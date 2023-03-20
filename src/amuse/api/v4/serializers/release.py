import logging
from datetime import timedelta, datetime

from django.utils import timezone
from django.db.models import Q
from rest_framework import serializers
from rest_framework.exceptions import ValidationError

from amuse.analytics import music_upload, rb_successful
from amuse.api.actions.release import (
    enforce_release_version,
    event_created,
    exclude_youtube_content_id_for_disallowed_genres,
    VerifyPendingReleasesCount,
    verify_user,
)
from amuse.api.base.validators import (
    validate_cover_art_filename,
    validate_language,
    validate_primary_artist_on_song,
    validate_no_duplicate_isrc,
)
from amuse.api.v4.serializers.coverart import CoverArtSerializer
from amuse.api.v4.serializers.genre import GenreSerializer
from amuse.api.v4.serializers.helpers import (
    create_royalty_splits,
    create_song_artist_invites,
    create_song_artists_roles,
    notify_release_owner_if_required,
)
from amuse.api.v4.serializers.release_artist_role import ReleaseArtistRoleSerializer
from amuse.api.v4.serializers.song import SongSerializer
from amuse.platform import PlatformHelper
from amuse.serializers import BitFieldField, StringMapField
from codes.models import ISRC
from countries.models import Country
from releases.models import (
    CoverArt,
    MetadataLanguage,
    Release,
    ReleaseArtistRole,
    Song,
    Store,
    cover_art_file_changed,
)
from releases.utils import queue_celery_tasks
from subscriptions.models import SubscriptionPlan
from users.models import ArtistV2
from users.models.user import User
from amuse.tasks import create_asset_labels, send_email_first_time_cid_use


logger = logging.getLogger(__name__)


class ReleaseListSerializer(serializers.ListSerializer):
    def to_representation(self, data):
        data = data.exclude(status=Release.STATUS_DELETED).prefetch_related(
            'upc', 'songs__songartistrole', 'songs__isrc', 'songs__genre'
        )
        return super().to_representation(data)


class ReleaseSerializer(serializers.Serializer):
    PENDING_APPROVAL_STATUSES = [
        Release.STATUS_SUBMITTED,
        Release.STATUS_PENDING,
        Release.STATUS_APPROVED,
        Release.STATUS_UNDELIVERABLE,
    ]
    NOT_APPROVED_STATUSES = [Release.STATUS_NOT_APPROVED, Release.STATUS_INCOMPLETE]
    MAPPED_PENDING_APPROVAL = 'pending_approval'
    MAPPED_NOT_APPROVED = 'not_approved'
    MAPPED_DELIVERED = 'delivered'
    MAPPED_RELEASED = 'released'
    MAPPED_TAKEDOWN = 'takedown'
    STATUS_UNKNOWN = 'unknown'

    MAPPED_STATUS_BY_ACTUAL_STATUS = {
        Release.STATUS_DELIVERED: MAPPED_DELIVERED,
        Release.STATUS_RELEASED: MAPPED_RELEASED,
        Release.STATUS_TAKEDOWN: MAPPED_TAKEDOWN,
    }

    id = serializers.IntegerField(read_only=True)
    name = serializers.CharField(max_length=255)
    type = StringMapField(mapping=Release.TYPE_CHOICES, read_only=True)
    created = serializers.DateTimeField(read_only=True)
    schedule_type = serializers.CharField(required=False, allow_null=False)
    release_date = serializers.DateField(required=False, allow_null=True)
    release_version = serializers.CharField(
        max_length=255, required=False, allow_null=True, allow_blank=True
    )
    original_release_date = serializers.DateField(required=False, allow_null=True)
    label = serializers.CharField(
        required=False,
        allow_null=True,
        allow_blank=True,
        max_length=Release.LABEL_MAX_LENGTH,
    )
    genre = GenreSerializer(read_only=True)
    status = serializers.CharField(read_only=True)
    # In order to avoid breaking the old version of the iOS app we return
    # "-" as a response of the upc field instead of null.
    upc = serializers.CharField(read_only=True, source="upc.code", default="-")

    cover_art = CoverArtSerializer(read_only=True)
    songs = SongSerializer(many=True)

    error_flags = BitFieldField(flags=Release.error_flags.items(), read_only=True)
    excluded_countries = serializers.ListField(
        source='excluded_country_codes',
        child=serializers.CharField(min_length=2, max_length=2),
    )
    excluded_stores = serializers.ListField(
        source='excluded_store_ids', child=serializers.IntegerField(min_value=1)
    )

    cover_art_filename = serializers.CharField(
        validators=[validate_cover_art_filename], write_only=True
    )

    language_code = serializers.CharField(
        write_only=True, required=False, allow_null=True, validators=[validate_language]
    )
    user_id = serializers.IntegerField(read_only=True)
    artist_id = serializers.IntegerField(write_only=True)
    artist_roles = ReleaseArtistRoleSerializer(many=True, read_only=True)
    link = serializers.CharField(read_only=True)
    include_pre_save_link = serializers.BooleanField(required=False, default=False)

    def to_representation(self, instance):
        data = super().to_representation(instance)
        status = int(data['status'])

        if status in ReleaseSerializer.PENDING_APPROVAL_STATUSES:
            mapped_status = ReleaseSerializer.MAPPED_PENDING_APPROVAL
        elif status in ReleaseSerializer.NOT_APPROVED_STATUSES:
            mapped_status = ReleaseSerializer.MAPPED_NOT_APPROVED
        else:
            mapped_status = ReleaseSerializer.MAPPED_STATUS_BY_ACTUAL_STATUS.get(
                status, ReleaseSerializer.STATUS_UNKNOWN
            )
        data['status'] = mapped_status
        if not data['release_date']:
            data['release_date'] = str(
                datetime.strptime(data['created'], "%Y-%m-%dT%H:%M:%S.%fZ").date()
            )
        data['schedule_type'] = Release.SCHEDULE_TYPES_MAP[int(data['schedule_type'])]

        return data

    def create(self, validated_data):
        user = self.context['request'].user
        verify_user(user)
        VerifyPendingReleasesCount.verify(user)
        songs = validated_data.pop('songs')
        language_code = validated_data.pop('language_code', None)

        if language_code:
            validated_data['meta_language'] = MetadataLanguage.by_code(language_code)

        cover_art_filename = validated_data.pop('cover_art_filename')
        excluded_country_codes = validated_data.pop('excluded_country_codes')
        excluded_store_ids = validated_data.pop('excluded_store_ids')

        artist_id = validated_data.pop('artist_id')
        artist_v2 = ArtistV2.objects.get(id=artist_id)

        schedule_type = validated_data.pop('schedule_type')
        release_date = validated_data.pop('release_date')

        release = Release.objects.create(
            user=artist_v2.owner,
            created_by=user,
            type=Release.get_type_for_track_count(len(songs)),
            schedule_type=schedule_type,
            release_date=release_date,
            **validated_data,
        )

        release.cover_art = CoverArt.objects.create(
            file=cover_art_filename, release=release, user=user
        )

        ReleaseArtistRole.objects.create(
            release=release,
            artist=artist_v2,
            role=ReleaseArtistRole.ROLE_PRIMARY_ARTIST,
            artist_sequence=1,
            main_primary_artist=True,
        )

        if excluded_country_codes:
            release.excluded_countries.set(
                Country.objects.filter(code__in=excluded_country_codes)
            )

        stores = Store.objects.active()
        if excluded_store_ids:
            stores = stores.exclude(pk__in=excluded_store_ids)
        release.stores.set(stores)
        acrcloud_store = Store.objects.filter(
            internal_name='acrcloud', active=False, admin_active=True
        ).first()
        if acrcloud_store:
            release.stores.add(acrcloud_store)

        for song_data in songs:
            genre = song_data.pop('genre')
            artists_roles_list = song_data.pop('artists_roles')
            artists_invites_list = song_data.pop('artists_invites', None)
            royalty_splits = song_data.pop('royalty_splits')
            isrc = song_data.pop('isrc', None)
            audio_s3_key = song_data.pop('audio_s3_key', None)
            audio_dropbox_link = song_data.pop('audio_dropbox_link', None)
            google_drive_auth_code = song_data.pop('audio_gdrive_auth_code', None)
            google_drive_file_id = song_data.pop('audio_gdrive_file_id', None)
            song_language_code = song_data.pop('language_code', None)
            song_audio_language_code = song_data.pop('audio_language_code', None)

            if song_language_code:
                song_data['meta_language'] = MetadataLanguage.by_code(
                    song_language_code
                )

            if song_audio_language_code:
                song_data['meta_audio_locale'] = MetadataLanguage.by_code(
                    song_audio_language_code
                )
            song = Song.objects.create(
                release=release,
                isrc=ISRC.objects.use(isrc),
                genre_id=genre.get('id'),
                **song_data,
            )

            main_primary_artist_id = release.main_primary_artist.id

            has_main_primary_artist_on_track = [
                True
                for item in artists_roles_list
                if (
                    item["artist_id"] == main_primary_artist_id
                    and "primary_artist" in item["roles"]
                )
            ]

            if not has_main_primary_artist_on_track:
                raise ValidationError(
                    {"non_field_errors": ["Main primary artist missing from track."]}
                )

            create_song_artists_roles(song, artists_roles_list, main_primary_artist_id)
            create_royalty_splits(user, song, royalty_splits)
            notify_release_owner_if_required(user, song, royalty_splits, artist_v2)
            if artists_invites_list:
                create_song_artist_invites(user, song, artists_invites_list)

            filename_extension = song_data.get('filename').split('.')[-1].lower()
            queue_celery_tasks(
                song.pk,
                audio_s3_key,
                audio_dropbox_link,
                google_drive_auth_code,
                google_drive_file_id,
                filename_extension,
            )

        self._include_yt_content_id_store(release, stores)

        if release.user.category is not User.CATEGORY_PRIORITY:
            exclude_youtube_content_id_for_disallowed_genres(release)
        release.genre = release.get_most_occuring_genre()
        enforce_release_version(release)
        release.save()
        event_created(self.context['request'], release)

        platform = PlatformHelper.from_request(self.context.get("request"))
        music_upload(user, platform)
        create_asset_labels.delay(release.id)

        event_data = {
            "release_id": release.id,
            "release_name": release.name,
            "main_primary_artist": release.main_primary_artist.name,
            "release_date": release.release_date
            if release.release_date
            else release.created,
            "schedule_type": release.schedule_type,
        }
        rb_successful(user.id, self.context.get("request"), event_data)

        if self._is_first_time_cid_use(user, release):
            data = {
                "user_id": user.id,
                "email": user.email,
                "receiver_first_name": user.first_name,
                "receiver_last_name": user.last_name,
            }
            send_email_first_time_cid_use.delay(data)

        return release

    def update(self, instance, validated_data):
        """
        We only allow cover_art_filename and release_date to be changed
        """
        if 'cover_art_filename' in validated_data:
            cover_art_filename = validated_data.get('cover_art_filename').rsplit(
                '/', 1
            )[-1]
            if cover_art_filename != instance.cover_art.file.name:
                logger.info(
                    'Updating coverart with id %d from \'%s\' to \'%s\''
                    % (
                        instance.cover_art.id,
                        instance.cover_art.file.name,
                        cover_art_filename,
                    )
                )
                instance.cover_art.file = cover_art_filename
                instance.cover_art.save()
                cover_art_file_changed(instance)

        if (
            'release_date' in validated_data
            and instance.schedule_type == Release.SCHEDULE_TYPE_STATIC
        ):
            release_date = validated_data.get('release_date')
            if release_date:
                instance.release_date = release_date
        elif instance.schedule_type == Release.SCHEDULE_TYPE_STATIC:
            # check release_date only if release_date is missing in request body
            today = timezone.now().date()
            earliest_date = today + timedelta(days=10)

            if instance.release_date < earliest_date:
                instance.release_date = earliest_date

        instance.save()
        return instance

    def validate_excluded_stores(self, excluded_store_ids):
        '''Pro stores should not be available for free user.'''
        user = self.context['request'].user

        if user.tier == User.TIER_FREE:
            pro_store_ids = Store.objects.filter(is_pro=True).values_list(
                'pk', flat=True
            )

            excluded_store_ids = list(set(excluded_store_ids + list(pro_store_ids)))

        return excluded_store_ids

    def validate_include_pre_save_link(self, include_pre_save_link):
        user = self.context['request'].user

        if user.tier == User.TIER_FREE and include_pre_save_link:
            raise ValidationError('Pre-save links are not available to Start Users')

        return include_pre_save_link

    def validate_schedule_type(self, schedule_type):
        if schedule_type:
            if schedule_type not in Release.SCHEDULE_TYPES_MAP.values():
                # When schedule_type: invalid type
                raise ValidationError('Invalid schedule type: %s' % schedule_type)
            elif (
                Release.SCHEDULE_TYPES_INV_MAP[schedule_type]
                == Release.SCHEDULE_TYPE_ASAP
            ):
                # When schedule_type: 'asap'
                schedule_type = Release.SCHEDULE_TYPE_ASAP
            else:
                # When schedule_type: 'static'
                schedule_type = Release.SCHEDULE_TYPE_STATIC
        else:
            # When schedule_type: None
            schedule_type = Release.SCHEDULE_TYPE_STATIC
        return schedule_type

    def validate_release_date(self, release_date):
        today = timezone.now().date()
        if self.instance is not None:
            # re-submitting the release
            earliest_date = today + timedelta(days=10)
        elif self.context['request'].user.tier in [
            SubscriptionPlan.TIER_PRO,
            SubscriptionPlan.TIER_PLUS,
        ]:
            # creating new pro release
            earliest_date = today + timedelta(days=10)
        else:
            # creating new free release
            earliest_date = today + timedelta(days=27)

        if release_date and release_date < earliest_date:
            raise ValidationError(
                'Earliest release date possible is %s'
                % earliest_date.strftime('%Y-%m-%d')
            )

        return release_date

    def validate_songs(self, attrs):
        if attrs:
            validate_primary_artist_on_song(attrs)
            validate_no_duplicate_isrc(attrs)
            attrs = self._enforce_sequence_integrity(attrs)
        return attrs

    def validate(self, validated_data):
        validated_data = super().validate(validated_data)
        user = self.context['request'].user
        yt_store_id = Store.get_yt_content_id_store().pk
        yt_music_store_id = Store.get_yt_music_store().pk
        user_tier = user.tier

        if validated_data.get('excluded_store_ids'):
            all_store_ids = list(
                Store.objects.filter(active=True).values_list('id', flat=True)
            )

            if sorted(validated_data['excluded_store_ids']) == sorted(all_store_ids):
                # Assign free stores to free user when all stores are excluded
                if user_tier == User.TIER_FREE:
                    pro_store_ids = list(
                        Store.objects.filter(is_pro=True, active=True).values_list(
                            'id', flat=True
                        )
                    )
                    validated_data['excluded_store_ids'] = pro_store_ids

        is_yt_content_id_store_excluded = yt_store_id in validated_data.get(
            'excluded_store_ids', []
        )
        is_yt_music_store_excluded = yt_music_store_id in validated_data.get(
            'excluded_store_ids', []
        )

        if is_yt_content_id_store_excluded and is_yt_music_store_excluded == False:
            # Add Youtube Content ID store if release contains song set to block/monetize
            yt_store_required = (Song.YT_CONTENT_ID_BLOCK, Song.YT_CONTENT_ID_MONETIZE)

            for song in validated_data['songs']:
                if song['youtube_content_id'] in yt_store_required:
                    if is_yt_content_id_store_excluded:
                        validated_data['excluded_store_ids'].remove(yt_store_id)
                    break

        if not self.instance:
            # validate artist_id exists
            artist_id = validated_data.get('artist_id')
            artist = ArtistV2.objects.filter(pk=artist_id).first()
            if not artist:
                raise ValidationError("Invalid main primary artist")

            store_validations = [
                {
                    "internal_names": ["audiomack"],
                    "excluded_store_ids": validated_data["excluded_store_ids"],
                    "func": self._no_audiomack_id_should_be_excluded,
                    "func_arg": artist,
                },
                {
                    "internal_names": ["tencent", "netease"],
                    "excluded_store_ids": validated_data["excluded_store_ids"],
                    "func": self._explicit_should_be_excluded,
                    "func_arg": validated_data["songs"],
                },
            ]

            invalid_store_ids = []

            for validation in store_validations:
                invalid_store_ids.extend(self._validate_stores(*validation.values()))

            validated_data['excluded_store_ids'].extend(invalid_store_ids)

            # custom labels are a PRO feature
            if user.tier != SubscriptionPlan.TIER_PRO:
                label = validated_data.get('label')
                if label:
                    if label != artist.name:
                        raise ValidationError('Custom labels are a PRO feature')
                else:
                    validated_data['label'] = artist.name

            # Prevent 'schedule_type' not in request
            validated_data['schedule_type'] = validated_data.get(
                'schedule_type', Release.SCHEDULE_TYPE_STATIC
            )

            # Validate combinations of release date, schedule type and subscription
            if validated_data['schedule_type'] is Release.SCHEDULE_TYPE_ASAP:
                # Prevent pre-save link for ASAP releases
                validated_data['include_pre_save_link'] = False
                if user.tier is not SubscriptionPlan.TIER_PRO:
                    raise ValidationError('ASAP releases are a PRO feature')
                else:
                    validated_data['release_date'] = None
            elif validated_data['schedule_type'] is Release.SCHEDULE_TYPE_STATIC:
                # Prevent 'release_date' not in request
                if not 'release_date' in validated_data:
                    raise ValidationError(
                        'Release date is required for static releases '
                    )

        return validated_data

    def _enforce_sequence_integrity(self, songs):
        """
        iOS 3.0.0 sends sequences starting with zero in some cases and this helper
        ensures that we always start sequences with 1.
        """
        sequence = [song["sequence"] for song in songs]

        if min(sequence) == 0:
            for song in songs:
                song["sequence"] += 1

        return songs

    def _include_yt_content_id_store(self, release, stores):
        """
        Will add yt_content_id_store to the included stores if:
            - YT CID is enabled on track level AND
            - Youtube Music store is enabled on release level
        """
        try:
            yt_content_id_store = Store.get_yt_content_id_store()
            yt_music_store = Store.get_yt_music_store()

            yt_content_id_monetized = release.songs.filter(
                youtube_content_id=Song.YT_CONTENT_ID_MONETIZE
            ).exists()
            yt_music_store_enabled = yt_music_store in stores

            if yt_content_id_monetized and yt_music_store_enabled:
                release.stores.add(yt_content_id_store)
        except Store.DoesNotExist:
            pass

    def _is_first_time_cid_use(self, user, release):
        new_release_cid_monetized = release.songs.filter(
            youtube_content_id=Song.YT_CONTENT_ID_MONETIZE
        ).exists()

        if not new_release_cid_monetized:
            return False

        used_content_id_before = Song.objects.filter(
            Q(release__created_by__id=user.id),
            ~Q(youtube_content_id=Song.YT_CONTENT_ID_NONE),
            ~Q(release__id=release.id),
        ).exists()
        return not used_content_id_before and new_release_cid_monetized

    def _has_explicit_tracks(self, songs):
        return any([s for s in songs if s["explicit"] == Song.EXPLICIT_TRUE])

    def _validate_stores(self, internal_names, excluded_store_ids, func, *args):
        """Validates list of stores with specified validator function and args.

        Args:
            internal_names (list): ["spotify", "tencent"]
            excluded_store_ids (list): [1, 2, 3]
            func (obj): Validator function returning a Boolean
            *args: Arguments for Validator function

        Returns:
            List of store_ids that failed validation.
        """
        store_ids = list(
            Store.objects.filter(
                internal_name__in=internal_names, active=True
            ).values_list("pk", flat=True)
        )

        invalid_store_ids = [
            store_id
            for store_id in store_ids
            if store_id not in excluded_store_ids and func(*args) is True
        ]

        return invalid_store_ids

    def _no_audiomack_id_should_be_excluded(self, artist):
        return True if not artist.audiomack_id else False

    def _explicit_should_be_excluded(self, songs):
        return True if self._has_explicit_tracks(songs) else False
