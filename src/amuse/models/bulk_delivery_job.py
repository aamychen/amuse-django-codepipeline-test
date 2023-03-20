import csv
import gc
import time
from logging import getLogger

from django.conf import settings
from django.contrib.postgres.fields import ArrayField
from django.core.exceptions import ValidationError
from django.db import models

from amuse.services.delivery.checks import get_store_delivery_checks
from amuse.services.release_delivery_info import ReleaseDeliveryInfo
from amuse.storages import S3Storage
from amuse.vendor.fuga.fuga_api import FugaAPIClient
from releases.models import Store, ReleaseArtistRole, FugaMetadata, Song, Release
from users.models import User

logger = getLogger(__name__)


def validate_file_extension(value):
    if not value.name.endswith('.csv'):
        raise ValidationError("Only CSV file is accepted")


class BulkDeliveryJob(models.Model):
    STATUS_CREATED = 0
    STATUS_PROCESSING = 1
    STATUS_COMPLETED = 2
    STATUS_FAILED = 3

    STATUS_OPTIONS = {
        STATUS_CREATED: 'created',
        STATUS_PROCESSING: 'processing',
        STATUS_COMPLETED: 'completed',
        STATUS_FAILED: 'failed',
    }

    JOB_TYPE_INSERT = 0
    JOB_TYPE_UPDATE = 1
    JOB_TYPE_TAKEDOWN = 2
    JOB_TYPE_FULL_UPDATE = 3

    JOB_TYPE_OPTIONS = {
        JOB_TYPE_INSERT: 'insert',
        JOB_TYPE_FULL_UPDATE: 'full update',
        JOB_TYPE_UPDATE: 'update metadata',
        JOB_TYPE_TAKEDOWN: 'takedown',
    }

    MAP_JOB_TYPE_TO_DELIVERY_COMMAND = {
        JOB_TYPE_INSERT: 'insert',
        JOB_TYPE_FULL_UPDATE: 'insert',
        JOB_TYPE_UPDATE: 'update',
        JOB_TYPE_TAKEDOWN: 'takedown',
    }

    MODE_ADD_RELEASE_STORES = 0
    MODE_OVERRIDE_RELEASE_STORES = 1
    MODE_ONLY_RELEASE_STORES = 2
    MODE_ONLY_FUGA_RELEASE_STORES = 3

    MODE_OPTIONS = {
        MODE_ADD_RELEASE_STORES: 'Add release stores',
        MODE_OVERRIDE_RELEASE_STORES: 'Override release stores',
        MODE_ONLY_RELEASE_STORES: 'Only release stores',
        MODE_ONLY_FUGA_RELEASE_STORES: 'Only fuga release stores',
    }

    def generate_file_name(self, filename):
        return str(int(time.time() * 1000)) + '.csv'

    input_file = models.FileField(
        upload_to=generate_file_name,
        storage=S3Storage(bucket_name=settings.AWS_BULK_DELIVERY_JOB_BUCKET_NAME),
        help_text='Upload csv file with all the release ids to be handled',
        validators=[validate_file_extension],
    )

    type = models.PositiveSmallIntegerField(
        default=JOB_TYPE_INSERT,
        choices=[(k, v) for k, v in JOB_TYPE_OPTIONS.items()],
        db_index=True,
        help_text='Type of bulk operation to perform',
    )

    store = models.ForeignKey(
        Store,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name='store_selected',
    )

    status = models.PositiveSmallIntegerField(
        default=STATUS_CREATED,
        choices=[(k, v) for k, v in STATUS_OPTIONS.items()],
        editable=False,
        db_index=True,
    )

    mode = models.PositiveSmallIntegerField(
        default=MODE_ADD_RELEASE_STORES,
        choices=[(k, v) for k, v in MODE_OPTIONS.items()],
        blank=False,
        db_index=True,
    )

    description = models.CharField(max_length=256, null=True, editable=False)

    user = models.ForeignKey(
        User, on_delete=models.SET_NULL, blank=True, null=True, editable=False
    )

    execute_at = models.DateTimeField(blank=True, null=True)
    date_created = models.DateTimeField(auto_now_add=True, editable=False)
    date_updated = models.DateTimeField(auto_now=True, editable=False)

    checks_to_override = ArrayField(models.CharField(max_length=256), default=list)
    ignore_release_status = models.BooleanField(default=False)

    youtube_content_id = models.PositiveSmallIntegerField(
        blank=True, null=True, default=None
    )

    class Meta:
        verbose_name_plural = 'Bulk Delivery Jobs'

    def get_release_and_song_ids(self):
        from releases.models.release import Release

        with self.input_file.open('r') as f:
            content = [line.decode('utf-8') for line in f.readlines()]
            rows = csv.DictReader(content)
            release_ids = []
            song_ids = []
            for row in rows:
                if "release_id" in row:
                    try:
                        release_ids.append(int(row["release_id"]))
                    except ValueError:
                        # We are just skipping invalid release ids and log them
                        logger.info(
                            f'BulkDeliveryJob {self.id} invalid release_id: {row["release_id"]}'
                        )
                elif "release__id" in row:
                    try:
                        release_ids.append(int(row["release__id"]))
                    except ValueError:
                        # We are just skipping invalid release ids and log them
                        logger.info(
                            f'BulkDeliveryJob {self.id} invalid release_id: {row["release__id"]}'
                        )
                elif "user_id" in row:
                    try:
                        user_id = int(row["user_id"])
                        user_release_ids = Release.objects.filter(
                            user_id=user_id
                        ).values_list('id', flat=True)
                        if user_release_ids:
                            release_ids.extend(user_release_ids)
                    except ValueError:
                        # We are just skipping invalid user ids and log them
                        logger.info(
                            f'BulkDeliveryJob {self.id} invalid user_id: {row["user_id"]}'
                        )
                elif "user_email" in row:
                    user_email = row["user_email"]
                    if not user_email:
                        continue
                    user = User.objects.filter(email=user_email).first()
                    if not user:
                        user = User.objects.filter(email=user_email.lower()).first()
                    if not user:
                        user = User.objects.filter(
                            email=user_email[0].lower() + user_email[1:]
                        ).first()
                    if not user:
                        user = User.objects.filter(
                            email=user_email[0].upper() + user_email[1:]
                        ).first()
                    if user:
                        user_release_ids = Release.objects.filter(
                            user_id=user.id
                        ).values_list('id', flat=True)
                        if user_release_ids:
                            release_ids.extend(user_release_ids)
                    else:
                        # We are just skipping invalid user_emails and log them
                        logger.info(
                            f'BulkDeliveryJob {self.id} invalid user_email: {user_email}'
                        )
                elif "artist_id" in row:
                    try:
                        artist_id = int(row["artist_id"])
                        artists_release_ids = ReleaseArtistRole.objects.filter(
                            artist_id=artist_id, main_primary_artist=True
                        ).values_list('release_id', flat=True)

                        if artists_release_ids:
                            release_ids.extend(artists_release_ids)

                    except ValueError:
                        # We are just skipping invalid user ids and log them
                        logger.info(
                            f'BulkDeliveryJob {self.id} invalid artist_id: {row["artist_id"]}'
                        )
                elif "isrc" in row:
                    try:
                        isrc = row["isrc"]
                        song = Song.objects.filter(isrc__code=isrc)
                        if song.exists():
                            release_ids.extend(song.values_list('release', flat=True))
                            song_ids.extend(song.values_list('id', flat=True))
                    except ValueError:
                        # Skip invalid ISRCs
                        logger.info(
                            f'BulkDeliveryJob {self.id} invalid ISRC: {row["isrc"]}'
                        )

            return sorted(list(set(song_ids))), sorted(list(set(release_ids)))

    def get_delivery_command(self):
        return self.MAP_JOB_TYPE_TO_DELIVERY_COMMAND[self.type]

    def set_status_and_description(self, status, description):
        self.status = status
        self.description = description
        self.save()

    def get_checks_after_override(self, checks):
        return [
            check
            for check in checks
            if check.__class__.__name__ not in self.checks_to_override
        ]

    def perform_checks(self, store: str, releases: list) -> list:
        from amuse.models.bulk_delivery_job_results import BulkDeliveryJobResult

        store_releases = []

        for release in releases:
            checks = [
                check(
                    release=release,
                    store=Store.from_internal_name(store),
                    operation=self.get_delivery_command(),
                )
                for check in get_store_delivery_checks(store)
            ]
            checks = self.get_checks_after_override(checks)

            success = True
            for check in checks:
                if not check.passing():
                    BulkDeliveryJobResult.objects.filter(
                        job=self,
                        release=release,
                        status=BulkDeliveryJobResult.STATUS_UNPROCESSED,
                    ).update(
                        store=Store.from_internal_name(store),
                        status=BulkDeliveryJobResult.STATUS_PREVENTED,
                        description=check.failure_message,
                    )
                    success = False
                    break
            if success:
                store_releases.append(release)
        return store_releases

    def passed_delivery_checks(self, release):
        from amuse.models.bulk_delivery_job_results import BulkDeliveryJobResult

        for store in release.stores.all():
            for check in get_store_delivery_checks(store.internal_name):
                if check.__name__ not in self.checks_to_override:
                    check_obj = check(
                        release=release,
                        store=store,
                        operation=self.get_delivery_command(),
                    )
                    if not check_obj.passing():
                        BulkDeliveryJobResult.objects.filter(
                            job=self,
                            release=release,
                            status=BulkDeliveryJobResult.STATUS_UNPROCESSED,
                        ).update(
                            store=store,
                            status=BulkDeliveryJobResult.STATUS_PREVENTED,
                            description=check_obj.failure_message,
                        )
                        return False
        return True

    def passed_mode_checks(self):
        if self.mode == BulkDeliveryJob.MODE_ONLY_FUGA_RELEASE_STORES:
            self.status = BulkDeliveryJob.STATUS_FAILED
            self.description = 'Cannot process this mode at this point in time'
            self.save()
            return False
        elif self.mode == BulkDeliveryJob.MODE_ONLY_RELEASE_STORES:
            if self.store:
                self.status = BulkDeliveryJob.STATUS_FAILED
                self.description = 'You cannot select a store when you select this mode'
                self.save()
                return False
        elif self.youtube_content_id is not None and not self.store:
            self.status = BulkDeliveryJob.STATUS_FAILED
            self.description = 'The store has to be set to \'Youtube Content ID\' when you\'ve chosen an option for Youtube content id update.'
            self.save()
            return False
        elif (
            self.youtube_content_id is None
            and self.store
            and self.store.internal_name == 'youtube_content_id'
        ):
            self.status = BulkDeliveryJob.STATUS_FAILED
            self.description = 'When you set the store to \'Youtube Content ID\', you should also select an option in order to update Youtube content id. '
            self.save()
            return False
        elif not self.store:
            self.status = BulkDeliveryJob.STATUS_FAILED
            self.description = 'You must also pick a store when you select this mode'
            self.save()
            return False
        self.status = BulkDeliveryJob.STATUS_PROCESSING
        self.description = 'Bulk operation is in progress'
        self.save()
        return True

    def release_status_checks(self, release_ids):
        from releases.models import Release
        from amuse.models.bulk_delivery_job_results import BulkDeliveryJobResult

        if not release_ids:
            self.status = BulkDeliveryJob.STATUS_FAILED
            self.description = 'No valid release_ids found'
            self.save()
            return None

        status_set = (
            Release.VALID_DELIVERY_STATUS_SET
            if self.ignore_release_status
            else Release.APPROVED_STATUS_SET
        )
        prevented_releases = (
            Release.objects.filter(pk__in=release_ids)
            .exclude(status__in=status_set)
            .values_list('pk', flat=True)
        )

        valid_status_release_ids = [
            release_id
            for release_id in release_ids
            if release_id not in prevented_releases
        ]

        releases = (
            Release.objects.filter(
                pk__in=valid_status_release_ids, status__in=status_set
            )
            .distinct()
            .values_list('pk', flat=True)
        )

        if prevented_releases:
            BulkDeliveryJobResult.objects.bulk_create(
                [
                    BulkDeliveryJobResult(
                        job=self,
                        release_id=release_id,
                        status=BulkDeliveryJobResult.STATUS_PREVENTED,
                        description='Release status is not in Approved, Delivered or Released state',
                    )
                    for release_id in prevented_releases
                ]
            )

        if not releases:
            self.status = BulkDeliveryJob.STATUS_COMPLETED
            self.description = 'Job completed'
            self.save()
            return None

        BulkDeliveryJobResult.objects.bulk_create(
            [
                BulkDeliveryJobResult(
                    job=self,
                    release_id=release_id,
                    status=BulkDeliveryJobResult.STATUS_UNPROCESSED,
                    description='Not processed yet',
                    store=self.store,
                )
                for release_id in releases
            ]
        )
        return releases

    def update_songs(self, songs):
        if self.youtube_content_id:
            for song in songs.all():
                song.youtube_content_id = self.youtube_content_id
                song.save()

    def process_songs(self, song_ids, release_ids):
        songs = None
        if self.youtube_content_id and song_ids:
            songs = Song.objects.filter(pk__in=song_ids, release__in=release_ids)
        elif self.youtube_content_id:
            songs = Song.objects.filter(release__in=release_ids)

        if songs:
            self.update_songs(songs)

    def process_releases(self, release_ids, song_ids):
        from amuse.services.delivery.helpers import deliver_batches
        from amuse.models.bulk_delivery_job_results import BulkDeliveryJobResult
        from amuse.vendor.fuga.helpers import perform_fuga_delete

        client = FugaAPIClient()
        delivery_type = self.get_delivery_command()
        releases = Release.objects.filter(pk__in=release_ids)

        if self.mode == BulkDeliveryJob.MODE_ADD_RELEASE_STORES:
            for release in releases:
                release.stores.add(self.store)
        if self.mode in [
            BulkDeliveryJob.MODE_ADD_RELEASE_STORES,
            BulkDeliveryJob.MODE_OVERRIDE_RELEASE_STORES,
        ]:
            self.process_songs(song_ids, release_ids)
            cleared_releases = self.perform_checks(self.store.internal_name, releases)
            batchsize = 10 if self.store and self.store.multi_batch_support else 1
            delay = 10 if self.store and self.store.multi_batch_support else 1
            deliver_batches(
                releases=cleared_releases,
                delivery_type=delivery_type,
                stores=[self.store.internal_name],
                batchsize=batchsize,
                delay=delay,
                job=self,
                user=self.user,
            )
        if self.mode == BulkDeliveryJob.MODE_ONLY_RELEASE_STORES:
            for release in releases:
                if not self.passed_delivery_checks(release):
                    continue
                release_delivery_info = ReleaseDeliveryInfo(release)
                stores = release_delivery_info.get_direct_delivery_channels(
                    delivery_type
                )
                if delivery_type == "takedown":
                    fuga_release = FugaMetadata.objects.filter(
                        status='PUBLISHED', release=release
                    ).first()
                    if fuga_release:
                        perform_fuga_delete(fuga_release)
                else:
                    stores = stores + release_delivery_info.get_fuga_delivery_channels(
                        "full_update" if delivery_type == "update" else delivery_type
                    )
                if stores:
                    deliver_batches(
                        releases=[release],
                        delivery_type=delivery_type,
                        delay=1,
                        job=self,
                        stores=stores,
                        user=self.user,
                    )
                else:
                    BulkDeliveryJobResult.objects.filter(
                        job=self,
                        release=release,
                        status=BulkDeliveryJobResult.STATUS_UNPROCESSED,
                    ).update(
                        status=BulkDeliveryJobResult.STATUS_SUCCESSFUL,
                        description="No stores found on direct delivery",
                    )

    def execute(self):
        from releases.models import Release

        song_ids, release_ids = self.get_release_and_song_ids()

        if not self.passed_mode_checks():
            return

        valid_release_ids = self.release_status_checks(release_ids)
        if not valid_release_ids:
            return

        # Bulk Delivery Job processing starts
        count = len(valid_release_ids)
        chunk_size = 50
        for start in range(0, count, chunk_size):
            end = start + chunk_size if start + chunk_size < count else count
            self.process_releases(valid_release_ids[start:end], song_ids)
            chunked_releases = None
            chunked_releases_songs = None
            gc.collect()

        self.status = BulkDeliveryJob.STATUS_COMPLETED
        self.description = 'Job completed'
        self.save()
