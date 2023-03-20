from datetime import datetime

from bitfield import BitField
from collections import Counter
from django.db import IntegrityError, models

from slayer.clientwrapper import get_release_with_license_info
from amuse.db.decorators import observable_fields, with_history

from codes.models import UPC
from countries.models import Country
from releases.managers import ReleaseManager
from users.models import User
from . import Genre, MetadataLanguage, Store


def release_completed(release):
    if not release or release.status is not Release.STATUS_SUBMITTED:
        return
    if not release.cover_art.file or not release.cover_art.file.name:
        return
    if not release.songs or not release.songs.count():
        return
    for song in release.songs.all():
        if not song.files or song.files.count() == 0:
            return
    release.status = Release.STATUS_PENDING
    release.save()
    from amuse.tasks import acrcloud_identify_song, post_slack_release_completed

    post_slack_release_completed.delay(release)

    for song in release.songs.all():
        acrcloud_identify_song.delay(song.id)

    # Trigger validation services
    from amuse.services.validation import validate

    validate(release)


@observable_fields(exclude=['genre', 'created_by', 'user', 'upc', 'meta_language'])
@with_history
class Release(models.Model):
    TYPE_ALBUM = 1
    TYPE_SINGLE = 2
    TYPE_EP = 3
    TYPE_CHOICES = ((TYPE_ALBUM, 'album'), (TYPE_SINGLE, 'single'), (TYPE_EP, 'ep'))

    APPROVAL_STATUS_PENDING = 0
    APPROVAL_STATUS_NOT_APPROVED = 1
    APPROVAL_STATUS_APPROVED = 2

    APPROVAL_STATUS_CHOICES = (
        (APPROVAL_STATUS_PENDING, 'Pending'),
        (APPROVAL_STATUS_NOT_APPROVED, 'Not Approved'),
        (APPROVAL_STATUS_APPROVED, 'Approved'),
    )

    DELIVERY_STATUS_PENDING = 0
    DELIVERY_STATUS_STARTED = 1
    DELIVERY_STATUS_SUCCESS = 2
    DELIVERY_STATUS_FAILED = 3

    DELIVERY_STATUS_CHOICES = (
        (DELIVERY_STATUS_PENDING, 'Pending'),
        (DELIVERY_STATUS_STARTED, 'Started'),
        (DELIVERY_STATUS_SUCCESS, 'Success'),
        (DELIVERY_STATUS_FAILED, 'Failed'),
    )

    STATUS_SUBMITTED = 1
    STATUS_INCOMPLETE = 2
    STATUS_PENDING = 3
    STATUS_APPROVED = 4
    STATUS_NOT_APPROVED = 5
    STATUS_DELIVERED = 6
    STATUS_UNDELIVERABLE = 7
    STATUS_RELEASED = 8
    STATUS_REJECTED = 9
    STATUS_TAKEDOWN = 10
    STATUS_DELETED = 11

    STATUS_CHOICES = (
        (STATUS_SUBMITTED, 'Submitted'),
        (STATUS_INCOMPLETE, 'Incomplete'),
        (STATUS_PENDING, 'Pending Approval'),
        (STATUS_APPROVED, 'Approved'),
        (STATUS_NOT_APPROVED, 'Not approved'),
        (STATUS_DELIVERED, 'Delivered'),
        (STATUS_UNDELIVERABLE, 'Undeliverable'),
        (STATUS_RELEASED, 'Released'),
        (STATUS_REJECTED, 'Rejected'),
        (STATUS_TAKEDOWN, 'Taken down'),
        (STATUS_DELETED, 'Deleted'),
    )

    PENDING_APPROVAL_STATUS_SET = [
        STATUS_SUBMITTED,
        STATUS_PENDING,
        STATUS_APPROVED,
        STATUS_UNDELIVERABLE,
    ]

    APPROVED_STATUS_SET = [STATUS_APPROVED, STATUS_DELIVERED, STATUS_RELEASED]

    VALID_DELIVERY_STATUS_SET = [
        STATUS_APPROVED,
        STATUS_DELIVERED,
        STATUS_RELEASED,
        STATUS_TAKEDOWN,
    ]

    LABEL_MAX_LENGTH = 120

    FLAGS = (('DISTRIBUTED_BEFORE', 'Content has been distributed before'),)

    ERROR_FLAGS = (
        ('artwork_social-media', 'Artwork: Social media logos'),
        ('artwork_text', 'Artwork: Text'),
        ('artwork_format', 'Artwork: Format'),
        ('artwork_size', 'Artwork: Size'),
        ('artwork_blurry', 'Artwork: Blurry'),
        ('explicit_parental-advisory', 'Explicit: Parental advisory logo'),
        ('titles_differs', 'Titles differs'),
        ('release_date-changed', 'Release date changed'),
        ('release_duplicate', 'Possible duplicate'),
        ("release_underage", "Underage"),
        ("rights_no-rights", "No Rights"),
        ("release_generic-artist-name", "Generic artist name"),
        ("release_misleading-artist-name", "Misleadning artist name"),
        ("artwork_logos-brands", "Artwork: Logos and brands"),
        ("artwork_primary-or-featured", "Artwork: Primary or Featured"),
        ("artwork_generic", "Artwork: Generic"),
        ("artwork_size-new", "Artwork: Size"),
        ("artwork_pa-logo-mismatch", "Artwork: PA mismatch"),
        ("metadata_symbols-or-emoji", "Metadata: Symbols/Emojis Error"),
        ("metadata_symbols-emoji-info", "Metadata: Symbols/Emojis Information"),
        ("metadata_generic-terms", "Metadata: Generic title"),
        ("compound-artist", "Compound Artist"),
    )

    ERROR_FLAGS_MAP = {error_key: error_text for error_key, error_text in ERROR_FLAGS}

    RELEASE_VERSIONS = {
        'Remix': 'Remixes',
        'Live': 'Live',
        'Remastered': 'Remastered',
        'Acoustic Version': 'Acoustic Versions',
        'Demo': 'Demo Versions',
        'Instrumental Version': 'Instrumental Versions',
        'Karaoke Version': 'Karaoke Versions',
        'Radio Edit': 'Radio Edits',
        'Extended Version': 'Extended Versions',
        'A Cappella': 'A Cappella',
        'Freestyle': 'Freestyle Versions',
    }

    SCHEDULE_TYPE_STATIC = 1
    SCHEDULE_TYPE_ASAP = 2
    SCHEDULE_TYPES = (
        (SCHEDULE_TYPE_STATIC, "static"),
        (SCHEDULE_TYPE_ASAP, "asap"),
    )
    SCHEDULE_TYPES_MAP = {
        key_number: type_text for key_number, type_text in SCHEDULE_TYPES
    }
    SCHEDULE_TYPES_INV_MAP = {
        type_text: key_number for key_number, type_text in SCHEDULE_TYPES
    }

    type = models.SmallIntegerField(choices=TYPE_CHOICES)

    name = models.CharField(max_length=255, blank=False, null=False)
    label = models.CharField(
        max_length=LABEL_MAX_LENGTH, blank=True, null=True, default=None
    )

    flags = BitField(flags=FLAGS)

    schedule_type = models.SmallIntegerField(
        choices=SCHEDULE_TYPES, default=SCHEDULE_TYPE_STATIC, blank=False, null=False
    )
    release_date = models.DateField(blank=True, null=True)
    release_version = models.CharField(max_length=255, blank=True, null=True)

    original_release_date = models.DateField(blank=True, null=True)

    link = models.CharField(max_length=255, blank=True, null=True)
    include_pre_save_link = models.BooleanField(default=False)

    completed = models.BooleanField(
        default=False,
        help_text='The release creation is complete. <strong>Must not</strong> be set manually.',
    )
    approved = models.BooleanField(
        default=False,
        help_text='The release is approved and ready for delivery. <strong>Must</strong> be set manually.',
    )

    delivery_status = models.SmallIntegerField(
        default=DELIVERY_STATUS_PENDING, choices=DELIVERY_STATUS_CHOICES
    )

    status = models.SmallIntegerField(default=STATUS_SUBMITTED, choices=STATUS_CHOICES)

    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    upc = models.ForeignKey(UPC, on_delete=models.CASCADE, null=True, blank=True)
    artists = models.ManyToManyField('users.ArtistV2', through='ReleaseArtistRole')

    error_flags = BitField(default=None, null=True, flags=ERROR_FLAGS)

    objects = ReleaseManager()

    @property
    def upc_code(self):
        if self.upc is not None:
            return self.upc.code

    #: The user who created this release
    user = models.ForeignKey(User, related_name='releases', on_delete=models.CASCADE)
    created_by = models.ForeignKey(
        User,
        related_name='created_releases',
        blank=True,
        null=True,
        on_delete=models.SET_NULL,
    )

    genre = models.ForeignKey(Genre, null=True, on_delete=models.CASCADE)

    excluded_countries = models.ManyToManyField(
        Country,
        blank=True,
        help_text='This is the countries to <strong>exclude</strong> from delivery.',
    )
    excluded_stores = models.ManyToManyField(
        Store,
        blank=True,
        help_text='This is the stores to <strong>exclude</strong> from delivery.',
        related_name='excluded_releases',
    )
    stores = models.ManyToManyField(
        Store,
        blank=True,
        help_text='Deliver release to these stores',
        verbose_name='Included Stores',
    )

    meta_language = models.ForeignKey(
        MetadataLanguage, null=True, blank=True, on_delete=models.CASCADE
    )

    def __str__(self):
        return self.name

    @property
    def countries_count(self):
        return self.included_countries.count()

    @property
    def excluded_country_codes(self):
        return self.excluded_countries.values_list('code', flat=True)

    @property
    def excluded_country_names(self):
        return self.excluded_countries.values_list('name', flat=True)

    @property
    def excluded_store_ids(self):
        return list(self.get_excluded_stores().values_list('pk', flat=True))

    @property
    def included_countries(self):
        return Country.objects.exclude(code__in=self.excluded_country_codes)

    @property
    def included_country_codes(self):
        return self.included_countries.values_list('code', flat=True)

    @property
    def included_internal_stores(self):
        """
        Used to get internal_name values that are mapped to stores in the
        release-delivery service and used for deliveries.
        """
        return self.stores.values_list('internal_name', flat=True)

    @property
    def was_delivered_with_new_system(self):
        """
        Releases delivered with the new delivery system have Batch objects. Old
        deliveries do not have them.
        """
        from amuse.models.deliveries import Batch

        return Batch.objects.filter(
            status=Batch.STATUS_SUCCEEDED, batchdelivery__releases__in=[self.pk]
        ).exists()

    @property
    def artist_roles(self):
        return self.releaseartistrole_set.all()

    @property
    def main_primary_artist(self):
        role = self.releaseartistrole_set.filter(
            role=ReleaseArtistRole.ROLE_PRIMARY_ARTIST, main_primary_artist=True
        ).first()

        return role.artist if role else None

    @classmethod
    def get_type_for_track_count(cls, track_count):
        # Maybe just put this as automatic behavior in .save?
        if track_count <= 3:
            return cls.TYPE_SINGLE
        elif track_count <= 6:
            return cls.TYPE_EP
        return cls.TYPE_ALBUM

    @property
    def has_invalid_artist_roles(self):
        from releases.models import SongArtistRole

        role_types = [
            SongArtistRole.ROLE_PRIMARY_ARTIST,
            SongArtistRole.ROLE_FEATURED_ARTIST,
        ]
        song_ids = list(self.songs.values_list("id", flat=True))

        has_primary_featured_artists = (
            SongArtistRole.objects.filter(song_id__in=song_ids, role__in=role_types)
            .values("song_id", "artist_id")
            .annotate(models.Count("artist_id"))
            .order_by()
            .filter(artist_id__count__gt=1)
        )

        return True if has_primary_featured_artists else False

    def get_excluded_stores(self):
        return Store.objects.exclude(pk__in=self.stores.values_list('pk', flat=True))

    def get_most_occuring_genre(self):
        # Maybe automatic in .save?
        genres = tuple(self.songs.values_list('genre', flat=True))
        return Genre.objects.get(pk=max(set(genres), key=genres.count))

    def set_status_deleted(self):
        if self.status in (
            self.STATUS_APPROVED,
            self.STATUS_DELIVERED,
            self.STATUS_RELEASED,
            self.STATUS_TAKEDOWN,
            self.STATUS_DELETED,
        ):
            return False

        self.status = self.STATUS_DELETED
        self.save()
        return True

    def save(self, *args, **kwargs):
        is_adding = self._state.adding

        if self.upc is None and self.status == self.STATUS_APPROVED:
            self.upc = UPC.objects.use(None)

        if (
            not self.release_date
            and self.status == Release.STATUS_APPROVED
            and self.schedule_type == Release.SCHEDULE_TYPE_ASAP
        ):
            self.release_date = datetime.now().date()

        super().save(*args, **kwargs)

        if is_adding:
            from amuse.tasks import post_slack_release_created

            post_slack_release_created.delay(self)

    @property
    def has_licensed_tracks(self):
        response = get_release_with_license_info(release_id=self.pk)
        if 'release' in response and 'active_agreement_ids' in response['release']:
            return bool(response['release']['active_agreement_ids'])

        return False

    def has_locked_splits(self):
        for song in self.songs.all():
            if song.royalty_splits.filter(is_locked=True).exists():
                return True
        return False

    has_locked_splits.boolean = True
    has_locked_splits.short_description = "In active FFWD Deal"

    @property
    def tiktok_excluded(self):
        return not self.stores.filter(name='TikTok').exists()

    @property
    def soundcloud_excluded(self):
        return not self.stores.filter(name='SoundCloud').exists()

    def get_last_insert(self, channel):
        from amuse.models.deliveries import BatchDelivery, BatchDeliveryRelease

        return BatchDeliveryRelease.objects.filter(
            release_id=self.pk,
            delivery__channel=channel,
            status=BatchDeliveryRelease.STATUS_SUCCEEDED,
            delivery__status=BatchDelivery.STATUS_SUCCEEDED,
            type=BatchDeliveryRelease.DELIVERY_TYPE_INSERT,
        ).last()

    def has_takedown_delivery(self, channel):
        from amuse.models.deliveries import BatchDelivery, BatchDeliveryRelease

        delivery = BatchDeliveryRelease.objects.filter(
            release_id=self.pk,
            delivery__channel=channel,
            status=BatchDeliveryRelease.STATUS_SUCCEEDED,
            delivery__status=BatchDelivery.STATUS_SUCCEEDED,
        ).last()

        if not delivery:
            return False

        return delivery.type == BatchDeliveryRelease.DELIVERY_TYPE_TAKEDOWN

    @classmethod
    def get_releases_by_id(cls, status_ids, release_ids, stores=None):
        filter_kwargs = {"status__in": status_ids, "id__in": release_ids}
        if stores:
            filter_kwargs["stores__internal_name__in"] = stores
        return cls.objects.filter(**filter_kwargs).distinct()

    def get_song_metalang_majority(self):
        langs = self.songs.values_list('meta_language', flat=True)
        if not langs:  # @TODO: use walrus when py38
            return None

        # Filter out `None` items
        langs = filter(None, langs)

        # Get the most common meta_language
        lang_id, _ = Counter(langs).most_common(1)[0]
        return MetadataLanguage.objects.get(pk=lang_id)

    def exclude_audiomack(self):
        if not self.main_primary_artist:
            return True
        return not self.main_primary_artist.audiomack_id


class PlatformInfo(models.Model):
    PLATFORM_ANDROID = 1
    PLATFORM_CHOICES = ((PLATFORM_ANDROID, 'Android'),)

    platform = models.SmallIntegerField(choices=PLATFORM_CHOICES)
    version = models.CharField(max_length=32)
    release = models.ForeignKey(Release, on_delete=models.CASCADE)


class Comments(models.Model):
    release = models.OneToOneField(
        Release, related_name='comments', on_delete=models.CASCADE
    )
    text = models.TextField(help_text='Internal comments about current release.')

    def __str__(self):
        return self.text

    class Meta:
        verbose_name_plural = 'Comments'


class ReleaseArtistRole(models.Model):
    ROLE_PRIMARY_ARTIST = 1
    ROLE_FEATURED_ARTIST = 2
    ROLE_CHOICES = (
        (ROLE_PRIMARY_ARTIST, 'primary_artist'),
        (ROLE_FEATURED_ARTIST, 'featured_artist'),
    )

    artist = models.ForeignKey('users.ArtistV2', on_delete=models.SET_NULL, null=True)
    release = models.ForeignKey('Release', on_delete=models.DO_NOTHING)
    role = models.SmallIntegerField(choices=ROLE_CHOICES)
    created = models.DateTimeField(auto_now_add=True)
    artist_sequence = models.SmallIntegerField(blank=False, null=True)
    main_primary_artist = models.BooleanField(null=True)

    class Meta:
        ordering = ['id']
        unique_together = ('artist', 'release')

    @staticmethod
    def get_role_for_keyword(keyword):
        """
        Using the keyword for controbutor role on a song, return the Release Role
        """
        if keyword == 'primary_artist':
            return ReleaseArtistRole.ROLE_PRIMARY_ARTIST
        else:
            return ReleaseArtistRole.ROLE_FEATURED_ARTIST

    def save(self, *args, **kwargs):
        if self.id is None and self.main_primary_artist is None:
            self.main_primary_artist = False

        release_has_main_primary_artist = ReleaseArtistRole.objects.filter(
            release=self.release, main_primary_artist=True
        ).exists()

        target_releaseartistrole_is_main_primary_artist = (
            ReleaseArtistRole.objects.filter(
                release=self.release, artist=self.artist, main_primary_artist=True
            ).exists()
        )

        if self.main_primary_artist and release_has_main_primary_artist:
            raise IntegrityError(
                'Main Primary Artist already exists. This Error also occurs if you modify already set Main Primary Artist.'
            )

        if (
            not self.main_primary_artist
            and target_releaseartistrole_is_main_primary_artist
        ):
            raise IntegrityError(
                'Chosen artist is main primary artist. This can not be unset.'
            )
        else:
            super().save(*args, **kwargs)


class ReleaseStoresHistory(models.Model):
    release = models.ForeignKey(Release, on_delete=models.CASCADE)
    stores = models.ManyToManyField(Store)
    created = models.DateTimeField(auto_now_add=True)


class ReleaseAsset(Release):
    class Meta:
        proxy = True
