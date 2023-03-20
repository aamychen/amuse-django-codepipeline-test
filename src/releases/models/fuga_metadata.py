import enum
from datetime import datetime, timezone
from enum import Enum
from time import sleep

from django.conf import settings
from django.db import models, transaction
from django.db.models import JSONField


class FugaStore(Enum):
    XITE = 1553828531
    BEATPORT = 89882
    SEVENDIGITAL = 247916
    AWA = 847103579
    BMAT = 1158892521
    FIZY = 1988507361
    JAXSTA_MUSIC = 1186352005
    JOOX = 1517454273
    KUACK_MEDIA = 1226212715
    LINE_MUSIC = 1232212955
    QOBUZ = 9940949
    TIM_MUSIC = 1207204780
    TOUCHTUNES = 1130831671
    UNITED_MEDIA_AGENCY = 1210987244
    KKBOX = 121452605
    TENCENT = 1461025062
    YANDEX_MUSIC = 1209287754
    XIAMI = 1234931270
    NETEASE_CLOUD = 1382854531
    KAKAO_MELON = 1686928319
    MUSIC_IN_AYOBA = 78395129
    JIOSAAVN = 316911752
    YOUTUBE_MUSIC_LEGACY = 49262307
    SPOTIFY = 746109
    APPLE_MUSIC = 1330598
    YOUTUBE_MUSIC = 13285026
    YOUTUBE_CONTENT_ID = 1048705
    DEEZER = 2100357
    TIDAL = 3440259
    AMAZON = 99268
    ANGHAMI = 20799134
    IMUSICA = 103725
    FACEBOOK = 1415672002
    INSTAGRAM = 1499657856
    NAPSTER = 103731
    NUUDAY = 464139
    PANDORA = 7851192


class MigrationStatus(enum.Enum):
    MARKED = "marked"
    SPOTIFY_STARTED = "spotify_started"
    SPOTIFY_COMPLETED = "spotify_completed"
    STARTED = "started"
    COMPLETED = "completed"
    DELETED = "deleted"
    BLOCKED = "blocked"


class FugaStatus(enum.Enum):
    NONE = "none"
    LIVE = "live"
    UNDER_MIGRATION = "under_migration"
    MIGRATED = "migrated"
    DELETED = "deleted"


class FugaMigrationWave(models.Model):
    description = models.CharField(
        max_length=120, blank=True, null=True, editable=False
    )


class FugaMetadata(models.Model):
    release = models.ForeignKey('releases.Release', on_delete=models.CASCADE)
    product_id = models.BigIntegerField(unique=True)

    status = models.CharField(max_length=64, blank=True, null=True, db_index=True)

    release_metadata = JSONField(null=True, blank=True)
    asset_metadata = JSONField(null=True, blank=True)
    delivery_instructions_metadata = JSONField(null=True, blank=True)
    spotify_metadata = JSONField(null=True, blank=True)

    delivery_history_extracted_at = models.DateTimeField(blank=True, null=True)
    migration_started_at = models.DateTimeField(blank=True, null=True, editable=False)
    migration_completed_at = models.DateTimeField(blank=True, null=True, editable=False)
    last_parsed_at = models.DateTimeField(blank=True, null=True)
    last_synced_at = models.DateTimeField(blank=True, null=True)
    updated_at = models.DateTimeField(auto_now=True, editable=False)
    created_at = models.DateTimeField(auto_now_add=True, editable=False)

    whitelisted = models.BooleanField(null=True, default=None)
    mark_to_be_deleted = models.BooleanField(null=True, default=None)
    delete_started_at = models.DateTimeField(blank=True, null=True, editable=False)

    apple_ready_to_migrate = models.BooleanField(
        null=True, default=None, editable=False, db_index=True
    )
    apple_migration_started_at = models.DateTimeField(
        blank=True, null=True, editable=False
    )
    apple_migration_completed_at = models.DateTimeField(
        blank=True, null=True, editable=False
    )
    apple_roles_match = models.BooleanField(
        null=True, default=None, editable=False, db_index=True
    )
    has_apple_ids = models.BooleanField(
        null=True, default=None, editable=False, db_index=True
    )

    spotify_ready_to_migrate = models.BooleanField(
        null=True, default=None, editable=False, db_index=True
    )
    spotify_migration_started_at = models.DateTimeField(
        blank=True, null=True, editable=False
    )
    spotify_migration_completed_at = models.DateTimeField(
        blank=True, null=True, editable=False
    )
    spotify_roles_match = models.BooleanField(
        null=True, default=None, editable=False, db_index=True
    )
    has_spotify_ids = models.BooleanField(
        null=True, default=None, editable=False, db_index=True
    )

    ready_to_migrate = models.BooleanField(
        null=True, default=None, editable=False, db_index=True
    )
    metadata_match = models.BooleanField(
        null=True, default=None, editable=False, db_index=True
    )
    roles_match = models.BooleanField(
        null=True, default=None, editable=False, db_index=True
    )
    song_metadata_match = models.BooleanField(
        null=True, default=None, editable=False, db_index=True
    )
    song_roles_match = models.BooleanField(
        null=True, default=None, editable=False, db_index=True
    )

    revenue_level = models.IntegerField(
        blank=True, null=True, db_index=True, editable=False
    )

    migration_wave = models.IntegerField(
        blank=True, null=True, db_index=True, editable=False
    )
    fuga_migration_wave = models.ForeignKey(
        FugaMigrationWave,
        on_delete=models.DO_NOTHING,
        editable=False,
        blank=True,
        null=True,
    )

    has_alternative_stores = models.BooleanField(
        null=True, default=None, editable=False, db_index=True
    )

    # Release metadata - to be extracted from json
    name = models.CharField(max_length=1024, blank=True, null=True, editable=False)
    upc = models.CharField(
        max_length=16, blank=True, null=True, db_index=True, editable=False
    )
    hashed_key = models.CharField(max_length=256, blank=True, null=True, editable=False)
    state = models.CharField(
        max_length=64, blank=True, null=True, db_index=True, editable=False
    )

    release_version = models.CharField(
        max_length=256, blank=True, null=True, editable=False
    )
    genre = models.CharField(max_length=256, blank=True, null=True, editable=False)
    subgenre = models.CharField(max_length=256, blank=True, null=True, editable=False)
    language = models.CharField(max_length=32, blank=True, null=True, editable=False)
    label = models.CharField(max_length=512, blank=True, null=True, editable=False)

    cover_width = models.IntegerField(
        blank=True, null=True, db_index=True, editable=False
    )
    cover_height = models.IntegerField(
        blank=True, null=True, db_index=True, editable=False
    )

    catalog_tier = models.CharField(
        max_length=64, blank=True, null=True, editable=False
    )
    release_format_type = models.CharField(
        max_length=64, blank=True, null=True, editable=False
    )
    product_type = models.CharField(
        max_length=64, blank=True, null=True, editable=False
    )
    compilation = models.BooleanField(blank=True, null=True, editable=False)
    total_assets = models.IntegerField(blank=True, null=True, editable=False)

    parental_advisory = models.BooleanField(blank=True, null=True, editable=False)
    parental_advisory_next = models.CharField(
        max_length=32, blank=True, null=True, editable=False
    )

    added_date = models.DateTimeField(blank=True, null=True, editable=False)
    created_date = models.DateTimeField(blank=True, null=True, editable=False)
    modified_date = models.DateTimeField(blank=True, null=True, editable=False)
    consumer_release_date = models.DateField(blank=True, null=True, editable=False)
    original_release_date = models.DateField(blank=True, null=True, editable=False)

    c_line_text = models.CharField(
        max_length=512, blank=True, null=True, editable=False
    )
    c_line_year = models.IntegerField(blank=True, null=True, editable=False)
    p_line_text = models.CharField(
        max_length=512, blank=True, null=True, editable=False
    )
    p_line_year = models.IntegerField(blank=True, null=True, editable=False)

    class Meta:
        verbose_name_plural = 'Fuga Metadata'

    def get_and_store_metadata(self, fuga_client):
        sleep(settings.FUGA_API_DELAY_IN_MS / 1000)
        self.release_metadata = fuga_client.get_product(self.product_id)
        sleep(settings.FUGA_API_DELAY_IN_MS / 1000)
        self.asset_metadata = fuga_client.get_product_assets(self.product_id)
        sleep(settings.FUGA_API_DELAY_IN_MS / 1000)
        self.delivery_instructions_metadata = fuga_client.get_delivery_instructions(
            self.product_id
        )
        self.last_parsed_at = datetime.now()
        self.save()

    def extract_stores(self):
        stores = []
        if not self.delivery_instructions_metadata.get("delivery_instructions", None):
            return None
        dsp_instructions = self.delivery_instructions_metadata["delivery_instructions"]
        for dsp_instruction in dsp_instructions:
            if dsp_instruction["state"] != "NOT_ADDED":
                fuga_store, created = FugaStores.objects.get_or_create(
                    external_id=dsp_instruction["dsp"]["id"],
                    name=dsp_instruction["dsp"]["name"],
                    is_iip_dds=dsp_instruction["dsp"]["is_iip_dds"],
                    is_ssf_dds=dsp_instruction["dsp"]["is_ssf_dds"],
                )
                stores.append(fuga_store)
        return stores


class FugaStores(models.Model):
    external_id = models.BigIntegerField(unique=True)
    name = models.CharField(max_length=256, blank=False, null=False, editable=False)
    is_iip_dds = models.BooleanField(blank=False, editable=False)
    is_ssf_dds = models.BooleanField(blank=False, editable=False)
    created_at = models.DateTimeField(auto_now_add=True, editable=False)
    has_delivery_service_support = models.BooleanField(default=False, editable=False)

    class Meta:
        verbose_name_plural = 'Fuga Stores'

    def __str__(self):
        return f"{self.name}"


class FugaDeliveryHistory(models.Model):
    external_id = models.BigIntegerField(unique=True)
    release = models.ForeignKey(
        'releases.Release', on_delete=models.CASCADE, editable=False
    )
    product_id = models.BigIntegerField(null=False, editable=False, db_index=True)
    fuga_store = models.ForeignKey(FugaStores, on_delete=models.CASCADE, editable=False)
    ddex_batch_id = models.BigIntegerField(
        blank=True, null=True, editable=False, db_index=True
    )
    action = models.CharField(
        max_length=64, blank=False, null=False, editable=False, db_index=True
    )
    state = models.CharField(
        max_length=64, blank=False, null=False, editable=False, db_index=True
    )
    executed_by = models.CharField(
        max_length=256, blank=True, null=True, editable=False, db_index=True
    )
    dated_at = models.DateTimeField(blank=False, null=False, editable=False)
    created_at = models.DateTimeField(auto_now_add=True, editable=False)

    class Meta:
        verbose_name_plural = 'Fuga Delivery History'

    @staticmethod
    def delete_previous_records(fuga_release, fuga_store):
        historical_records = FugaDeliveryHistory.objects.filter(
            product_id=fuga_release.product_id, fuga_store=fuga_store
        )
        if historical_records:
            historical_records.delete()

    @staticmethod
    def get_new_records(fuga_release, fuga_store, records):
        latest_historical_record = (
            FugaDeliveryHistory.objects.filter(
                product_id=fuga_release.product_id, fuga_store=fuga_store
            )
            .order_by('-dated_at')
            .first()
        )
        if latest_historical_record:
            return [
                record
                for record in records
                if int(record['id']) > latest_historical_record.external_id
            ]
        return records

    @staticmethod
    def parse_fuga_delivery_feed_for_dsp(fuga_release, fuga_store, records):
        FugaDeliveryHistory.objects.bulk_create(
            [
                FugaDeliveryHistory(
                    external_id=record['id'],
                    release=fuga_release.release,
                    product_id=fuga_release.product_id,
                    fuga_store=fuga_store,
                    ddex_batch_id=record['ddexBatchId'],
                    action=record['action'],
                    state=record['state'],
                    executed_by=record['user'].get('label', None),
                    dated_at=datetime.fromisoformat(record['date']).replace(
                        tzinfo=timezone.utc
                    ),
                )
                for record in records
            ]
        )

    @staticmethod
    @transaction.atomic
    def sync_records_from_fuga(fuga_release, fuga_store, records):
        from releases.models.release_store_delivery_status import (
            ReleaseStoreDeliveryStatus,
        )

        if not records:
            return
        new_records = FugaDeliveryHistory.get_new_records(
            fuga_release, fuga_store, records
        )
        if not new_records:
            return
        FugaDeliveryHistory.parse_fuga_delivery_feed_for_dsp(
            fuga_release, fuga_store, new_records
        )
        latest_confirmed_delivery = (
            FugaDeliveryHistory.objects.filter(
                product_id=fuga_release.product_id,
                fuga_store=fuga_store,
                state='DELIVERED',
            )
            .order_by('-dated_at')
            .first()
        )
        if not latest_confirmed_delivery:
            return
        ReleaseStoreDeliveryStatus.objects.update_or_create(
            release_id=fuga_release.release_id,
            fuga_store=fuga_store,
            defaults={
                "status": ReleaseStoreDeliveryStatus.STATUS_TAKEDOWN
                if latest_confirmed_delivery.action == "TAKEDOWN"
                else ReleaseStoreDeliveryStatus.STATUS_DELIVERED,
                "latest_fuga_delivery_log": latest_confirmed_delivery,
                "delivered_at": latest_confirmed_delivery.dated_at,
            },
        )


class FugaPerson(models.Model):
    external_id = models.BigIntegerField(unique=True)
    name = models.CharField(
        max_length=1024, blank=True, null=True, editable=False, db_index=True
    )


class FugaArtist(models.Model):
    external_id = models.BigIntegerField(unique=True)
    name = models.CharField(
        max_length=1024, blank=True, null=True, editable=False, db_index=True
    )
    apple_id = models.CharField(
        max_length=1024, blank=True, null=True, editable=False, db_index=True
    )
    spotify_id = models.CharField(
        max_length=1024, blank=True, null=True, editable=False, db_index=True
    )
    parsed_at = models.DateTimeField(
        blank=True, null=True, editable=False, db_index=True
    )

    def parse_organizations(self, organizations_for_artist):
        if organizations_for_artist:
            for organization in organizations_for_artist:
                if organization["issuingOrganization"]["name"] == "Spotify":
                    self.spotify_id = organization["identifier"]
                elif organization["issuingOrganization"]["name"] == "Apple Music":
                    self.apple_id = organization["identifier"]
        self.parsed_at = datetime.now()
        self.save()


class FugaProductArtist(models.Model):
    release_id = models.BigIntegerField(db_index=True)
    fuga_product_id = models.BigIntegerField(db_index=True)
    fuga_artist_id = models.BigIntegerField(db_index=True)
    sequence = models.IntegerField()
    primary = models.BooleanField(null=True, default=None, editable=False)
    matched_artist_id = models.BigIntegerField(null=True, default=None, db_index=True)
    roles_match = models.BooleanField(
        null=True, default=None, editable=False, db_index=True
    )
    apple_id = models.CharField(
        max_length=1024, blank=True, null=True, editable=False, db_index=True
    )
    spotify_id = models.CharField(
        max_length=1024, blank=True, null=True, editable=False, db_index=True
    )


class FugaAsset(models.Model):
    external_id = models.BigIntegerField(unique=True)
    isrc = models.CharField(
        max_length=16, blank=True, null=True, editable=False, db_index=True
    )
    name = models.CharField(max_length=1024, blank=True, null=True, editable=False)
    duration = models.IntegerField(blank=True, null=True, editable=False)
    language = models.CharField(max_length=32, blank=True, null=True, editable=False)
    sequence = models.IntegerField(blank=True, null=True, editable=False)
    type = models.CharField(max_length=64, blank=True, null=True, editable=False)
    genre = models.CharField(max_length=256, blank=True, null=True, editable=False)
    subgenre = models.CharField(max_length=256, blank=True, null=True, editable=False)
    has_video = models.BooleanField(null=True, default=None, editable=False)
    has_lyrics = models.BooleanField(null=True, default=None, editable=False)
    rights_claim = models.CharField(
        max_length=256, blank=True, null=True, editable=False
    )
    modified_date = models.DateTimeField(blank=True, null=True, editable=False)
    created_date = models.DateTimeField(blank=True, null=True, editable=False)

    # Audio related fields
    audio_id = models.BigIntegerField(
        blank=True, null=True, editable=False, db_index=True
    )
    audio_duration = models.IntegerField(blank=True, null=True, editable=False)
    audio_bit_depth = models.IntegerField(blank=True, null=True, editable=False)
    audio_file_size = models.BigIntegerField(blank=True, null=True, editable=False)
    audio_mime_type = models.CharField(
        max_length=128, blank=True, null=True, editable=False
    )
    audio_vault_hook = models.CharField(
        max_length=256, blank=True, null=True, editable=False
    )
    audio_modified_date = models.DateTimeField(blank=True, null=True, editable=False)
    audio_created_date = models.DateTimeField(blank=True, null=True, editable=False)
    audio_has_uploaded = models.BooleanField(null=True, default=None, editable=False)
    audio_sampling_rate = models.IntegerField(blank=True, null=True, editable=False)
    audio_original_filename = models.CharField(
        max_length=256, blank=True, null=True, editable=False
    )
    audio_number_of_channels = models.IntegerField(
        blank=True, null=True, editable=False
    )

    asset_version = models.CharField(
        max_length=256, blank=True, null=True, editable=False
    )
    p_line_text = models.CharField(
        max_length=256, blank=True, null=True, editable=False
    )
    p_line_year = models.IntegerField(blank=True, null=True, editable=False)
    audio_locale = models.CharField(
        max_length=256, blank=True, null=True, editable=False
    )
    preorder_type = models.CharField(
        max_length=256, blank=True, null=True, editable=False
    )
    preview_start = models.IntegerField(blank=True, null=True, editable=False)
    preview_length = models.IntegerField(blank=True, null=True, editable=False)
    allow_preorder = models.BooleanField(null=True, default=None, editable=False)
    allow_preorder_preview = models.BooleanField(
        null=True, default=None, editable=False
    )
    available_separately = models.BooleanField(null=True, default=None, editable=False)

    display_artist = models.CharField(
        max_length=1024, blank=True, null=True, editable=False
    )

    parental_advisory = models.BooleanField(null=True, default=None, editable=False)
    parental_advisory_next = models.CharField(
        max_length=64, blank=True, null=True, editable=False
    )
    recording_year = models.IntegerField(blank=True, null=True, editable=False)

    metadata_match = models.BooleanField(
        null=True, default=None, editable=False, db_index=True
    )
    roles_match = models.BooleanField(
        null=True, default=None, editable=False, db_index=True
    )

    spotify_metadata = JSONField(null=True, blank=True)


class FugaProductAssetArtist(models.Model):
    release_id = models.BigIntegerField(db_index=True)
    fuga_product_id = models.BigIntegerField(db_index=True)
    fuga_asset_id = models.BigIntegerField(db_index=True)
    fuga_artist_id = models.CharField(
        max_length=1024, blank=True, null=True, editable=False
    )
    fuga_artist_id_as_int = models.BigIntegerField(
        blank=True, null=True, editable=False, db_index=True
    )
    fuga_person_id = models.BigIntegerField(
        blank=True, null=True, editable=False, db_index=True
    )

    role = models.CharField(
        max_length=128, blank=True, null=True, editable=False, db_index=True
    )
    sequence = models.IntegerField()
    primary = models.BooleanField(
        null=True, default=None, editable=False, db_index=True
    )
    artist_name = models.CharField(
        max_length=1024, blank=True, null=True, editable=False, db_index=True
    )
    matched_artist_id = models.BigIntegerField(null=True, default=None, db_index=True)
    roles_match = models.BooleanField(
        null=True, default=None, editable=False, db_index=True
    )
    apple_id = models.CharField(
        max_length=1024, blank=True, null=True, editable=False, db_index=True
    )
    spotify_id = models.CharField(
        max_length=1024, blank=True, null=True, editable=False, db_index=True
    )


class FugaProductAsset(models.Model):
    release_id = models.BigIntegerField(db_index=True)
    fuga_product_id = models.BigIntegerField(db_index=True)
    fuga_asset_id = models.BigIntegerField(db_index=True)
    sequence = models.IntegerField()
    matched_song_id = models.BigIntegerField(null=True, default=None, db_index=True)
    metadata_match = models.BooleanField(
        null=True, default=None, editable=False, db_index=True
    )
    roles_match = models.BooleanField(
        null=True, default=None, editable=False, db_index=True
    )
    spotify_roles_match = models.BooleanField(
        null=True, default=None, editable=False, db_index=True
    )
    has_spotify_ids = models.BooleanField(
        null=True, default=None, editable=False, db_index=True
    )


class FugaMismatch(models.Model):
    release_id = models.BigIntegerField(db_index=True)
    fuga_product_id = models.BigIntegerField(db_index=True)
    fuga_asset_id = models.BigIntegerField(
        null=True, default=None, editable=False, db_index=True
    )
    mismatch_attribute = models.CharField(
        max_length=1024, blank=True, null=True, editable=False, db_index=True
    )
    jarvis_value = models.CharField(
        max_length=1024, blank=True, null=True, editable=False
    )
    fuga_value = models.CharField(
        max_length=1024, blank=True, null=True, editable=False
    )

    class Meta:
        verbose_name_plural = 'Fuga mismatches'


class FugaGenre(models.Model):
    name = models.CharField(max_length=120, blank=True, null=True, editable=False)
    matched_genre_id = models.BigIntegerField(null=True, default=None, db_index=True)


class FugaMigrationReleaseStore(models.Model):
    fuga_metadata = models.ForeignKey(FugaMetadata, on_delete=models.CASCADE)
    release = models.ForeignKey('releases.Release', on_delete=models.CASCADE)
    store = models.ForeignKey('releases.Store', on_delete=models.CASCADE)
