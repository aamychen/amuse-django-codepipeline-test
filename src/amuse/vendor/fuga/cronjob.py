import logging
from datetime import datetime, timedelta
from ftplib import FTP
from time import sleep
from typing import List

from django.conf import settings

from amuse.services.delivery.helpers import deliver_batches
from amuse.vendor.fuga.delivery import FugaFTPConnection
from amuse.vendor.fuga.fuga_api import FugaAPIClient
from amuse.vendor.fuga.helpers import sync_fuga_delivery_data, perform_fuga_delete
from amuse.vendor.spotify.spotify_atlas_api import SpotifyAtlasAPI
from amuse.vendor.zendesk import api as zendesk
from releases.models import Release, Comments, ReleaseStoreDeliveryStatus, Store
from releases.models.fuga_metadata import (
    FugaMetadata,
    FugaDeliveryHistory,
    FugaAsset,
    FugaProductAsset,
    FugaMigrationReleaseStore,
)
from users.models import User

logger = logging.getLogger(__name__)
INGESTION_FAILED_DIR = '/ingestion_failed'
DATETIME_FORMAT = '%Y-%m-%d %H:%M'


def update_ingestion_failed_releases():
    try:
        with FugaFTPConnection() as ftp_connection:
            upc_codes = failed_release_upc_codes(ftp_connection)

        updated_upc_codes = mark_releases_as_undeliverable(upc_codes)

        if not updated_upc_codes:
            return

        with FugaFTPConnection() as ftp_connection:
            remove_ingestion_failed_releases(ftp_connection, updated_upc_codes)
    except Exception as e:
        logger.warning(
            f"FUGA update ingestion failed releases FAILED with error {str(e)}"
        )


def failed_release_upc_codes(ftp_connection: FTP):
    ftp_connection.cwd(INGESTION_FAILED_DIR)

    upc_codes = ftp_connection.nlst()

    return upc_codes


def mark_releases_as_undeliverable(upc_codes: List[str]):
    def release_comment(r):
        if hasattr(r, 'comments'):
            c = r.comments
        else:
            c = Comments(release=r, text='')

        comment_text = (
            f'{datetime.now().strftime(DATETIME_FORMAT)}: FUGA ingestion failed'
        )

        c.text = f'{comment_text}\r\n\r\n{c.text}'

        return c

    successful_upc_codes = []

    for upc_code in upc_codes:
        try:
            release = Release.objects.filter(
                upc__code=upc_code, status=Release.STATUS_DELIVERED
            ).first()

            if release:
                release.status = Release.STATUS_UNDELIVERABLE

                comment = release_comment(release)

                release.save()
                comment.save()

            successful_upc_codes.append(upc_code)
        except Exception:
            logger.exception(
                'Failed to update release with UPC %s to Undeliverable', upc_code
            )

    return successful_upc_codes


def remove_ingestion_failed_releases(ftp_connection: FTP, upc_codes: List[str]):
    def clear_directory(directory_name):
        for filename in ftp_connection.nlst(directory_name):
            ftp_connection.delete(f'{directory_name}/{filename}')

    for upc_code in upc_codes:
        try:
            directory = f'{INGESTION_FAILED_DIR}/{upc_code}'
            clear_directory(directory)

            ftp_connection.rmd(directory)
        except Exception:
            logger.exception('Failed to remove the FTP directory for UPC %s', upc_code)


def parse_releases_from_fuga():
    fuga_client = FugaAPIClient()
    unparsed_fuga_releases = FugaMetadata.objects.filter(
        last_parsed_at__isnull=True
    ).order_by('-id')[: settings.FUGA_PARSER_NUM_RELEASES]
    for fuga_release in unparsed_fuga_releases:
        fuga_release.get_and_store_metadata(fuga_client)


def parse_dsp_history_from_fuga(reverse=None):
    fuga_client = FugaAPIClient()
    id_ordering = 'id' if reverse else '-id'
    releases_with_unparsed_history = FugaMetadata.objects.filter(
        last_parsed_at__isnull=False, delivery_history_extracted_at__isnull=True
    ).order_by(id_ordering)[: settings.FUGA_PARSER_NUM_RELEASES_FOR_DSP_HISTORY]
    for fuga_release in releases_with_unparsed_history:
        for fuga_store in fuga_release.extract_stores():
            records = fuga_client.get_delivery_history_for_dsp(
                fuga_release.product_id, fuga_store.external_id
            )
            FugaDeliveryHistory.delete_previous_records(fuga_release, fuga_store)
            FugaDeliveryHistory.parse_fuga_delivery_feed_for_dsp(
                fuga_release, fuga_store, records
            )
            sleep(settings.FUGA_API_DELAY_IN_MS / 1000)
        fuga_release.delivery_history_extracted_at = datetime.now()
        fuga_release.save()


def parse_fuga_releases_from_spotify(reverse=None, num_releases=1):
    client = SpotifyAtlasAPI()
    id_ordering = 'id' if reverse else '-id'
    fuga_releases = FugaMetadata.objects.filter(
        status='PUBLISHED', spotify_metadata__isnull=True
    ).order_by(id_ordering)[:num_releases]
    for fuga_release in fuga_releases:
        logger.info(
            "Parsing spotify data for fuga release: %s" % fuga_release.release_id
        )
        results = client.search_album_by_upc(fuga_release.upc)
        if len(results) == 0:
            fuga_release.spotify_metadata = {"status": "not_found"}
            fuga_release.save()
        elif len(results) == 1:
            album_spotify_id = results[0].get("uri", None)
            if not album_spotify_id:
                fuga_release.spotify_metadata = {"status": "no_spotify_album_uri"}
                fuga_release.save()
                continue
            album_data = client.get_album(album_spotify_id)
            if not album_data or not album_data.get("effectiveData", None):
                fuga_release.spotify_metadata = {"status": "no_album_data"}
                fuga_release.save()
                continue
            tracks = album_data["effectiveData"].get("tracks", None)
            if not tracks:
                fuga_release.spotify_metadata = {"status": "no_tracks"}
                fuga_release.save()
                continue
            fuga_product_assets = FugaProductAsset.objects.filter(
                fuga_product_id=fuga_release.product_id
            )
            try:
                fuga_assets = [
                    FugaAsset.objects.get(external_id=fuga_product_asset.fuga_asset_id)
                    for fuga_product_asset in fuga_product_assets
                ]
            except FugaAsset.DoesNotExist:
                fuga_release.spotify_metadata = {"status": "no_asset_found"}
                fuga_release.save()
                continue
            fuga_asset_dict = {asset.isrc: asset for asset in fuga_assets}
            logger.info(
                "Parsing spotify data of {} tracks for fuga release: {}".format(
                    len(fuga_assets), fuga_release.release_id
                )
            )
            for track in tracks:
                track_data = client.get_album_track(album_spotify_id, track["uri"])
                fuga_asset = fuga_asset_dict.get(
                    track_data["effectiveData"]["isrc"], None
                )
                if not fuga_asset:
                    continue
                fuga_asset.spotify_metadata = track_data
                fuga_asset.save()
                sleep(settings.FUGA_API_DELAY_IN_MS / 1000)
            fuga_release.spotify_metadata = album_data
            fuga_release.save()
        else:
            fuga_release.spotify_metadata = {"status": "duplicate"}
            fuga_release.save()
        sleep(settings.FUGA_API_DELAY_IN_MS / 1000)
    logger.info("Job parse_fuga_releases_from_spotify completed")


def sync_fuga_releases(
    num_releases=100,
    non_synced=None,
    confirm_deleted=None,
    wave=None,
    force_sync=None,
    days=7,
    releases=None,
):
    if releases:
        fuga_releases = FugaMetadata.objects.filter(release_id__in=releases)
    elif wave:
        if non_synced:
            fuga_releases = FugaMetadata.objects.filter(
                fuga_migration_wave__id=wave, last_synced_at__isnull=True
            )[:num_releases]
        elif force_sync:
            fuga_releases = FugaMetadata.objects.filter(
                fuga_migration_wave__id=wave,
                last_synced_at__lte=datetime.now() - timedelta(days=days),
            )[:num_releases]
        else:
            fuga_releases = FugaMetadata.objects.filter(
                fuga_migration_wave__id=wave, last_synced_at__isnull=False
            )[:num_releases]
    elif non_synced:
        fuga_releases = FugaMetadata.objects.filter(
            status='PUBLISHED', last_synced_at__isnull=True
        )[:num_releases]
    elif confirm_deleted:
        fuga_releases = FugaMetadata.objects.filter(
            status='PUBLISHED',
            delete_started_at__lte=datetime.now() - timedelta(hours=1),
        )[:num_releases]
    else:
        fuga_releases = FugaMetadata.objects.filter(
            status='PUBLISHED',
            last_synced_at__lte=datetime.now() - timedelta(days=days),
        ).order_by('last_synced_at')[:num_releases]
    sync_fuga_delivery_data(fuga_releases)


def _fuga_spotify_direct_deliver_batch(fuga_releases, store, user):
    releases = [fuga_release.release for fuga_release in fuga_releases]
    for release in releases:
        if store not in release.stores.all():
            release.stores.add(store)
    try:
        deliver_batches(
            releases=releases,
            delivery_type='insert',
            stores=[store.internal_name],
            user=user,
        )
        now = datetime.now()
        for fuga_release in fuga_releases:
            fuga_release.spotify_migration_started_at = now
        FugaMetadata.objects.bulk_update(
            fuga_releases, ["spotify_migration_started_at"]
        )
    except Exception:
        for fuga_release in fuga_releases:
            fuga_release.ready_to_migrate = False
        FugaMetadata.objects.bulk_update(fuga_releases, ["ready_to_migrate"])


def fuga_spotify_direct_deliver(user_id=None, num_releases=100, wave=None):
    user = User.objects.get(id=user_id) if user_id else None  # Define when scheduled
    fuga_client = FugaAPIClient()
    dd_spotify_store = Store.from_internal_name("spotify")
    fuga_spotify_store = dd_spotify_store.fuga_store

    fuga_releases = FugaMetadata.objects.filter(
        status='PUBLISHED',
        ready_to_migrate=True,
        spotify_ready_to_migrate=True,
        spotify_migration_started_at__isnull=True,
        whitelisted__isnull=True,
        fuga_migration_wave__id=wave,
    )[:num_releases]
    batch_releases = []
    for fuga_release in fuga_releases:
        if fuga_release.release.status not in [
            Release.STATUS_APPROVED,
            Release.STATUS_DELIVERED,
            Release.STATUS_RELEASED,
        ]:
            # Release in an unacceptable status for migration
            fuga_release.spotify_ready_to_migrate = False
            fuga_release.ready_to_migrate = False
            fuga_release.save()
            continue

        # Sync latest historical records for Spotify from Fuga
        records = fuga_client.get_delivery_history_for_dsp(
            fuga_release.product_id, fuga_spotify_store.external_id
        )
        FugaDeliveryHistory.sync_records_from_fuga(
            fuga_release, fuga_spotify_store, records
        )

        # Check
        fuga_delivery_status = ReleaseStoreDeliveryStatus.objects.filter(
            release=fuga_release.release, fuga_store=fuga_spotify_store
        ).first()
        if (
            fuga_delivery_status
            and fuga_delivery_status.status
            == ReleaseStoreDeliveryStatus.STATUS_DELIVERED
        ):
            batch_releases.append(fuga_release)
            if len(batch_releases) >= dd_spotify_store.batch_size:
                _fuga_spotify_direct_deliver_batch(
                    batch_releases, dd_spotify_store, user
                )
                batch_releases = []
        else:
            # Release is not live on Spotify via Fuga feed - Mark spotify completed
            fuga_release.spotify_ready_to_migrate = False
            fuga_release.spotify_migration_completed_at = datetime.now()
            fuga_release.save()
    if batch_releases:
        _fuga_spotify_direct_deliver_batch(batch_releases, dd_spotify_store, user)


def fuga_spotify_takedown(num_releases=100, wave=None):
    fuga_client = FugaAPIClient()
    dd_spotify_store = Store.from_internal_name("spotify")
    fuga_spotify_store = dd_spotify_store.fuga_store
    fuga_releases = FugaMetadata.objects.filter(
        status='PUBLISHED',
        ready_to_migrate=True,
        spotify_ready_to_migrate=True,
        spotify_migration_started_at__lte=datetime.now() - timedelta(days=3),
        spotify_migration_completed_at__isnull=True,
        fuga_migration_wave__id=wave,
    )[:num_releases]
    for fuga_release in fuga_releases:
        # Check
        dd_delivery_status = ReleaseStoreDeliveryStatus.objects.filter(
            release=fuga_release.release, store=dd_spotify_store
        ).first()
        if (
            dd_delivery_status
            and dd_delivery_status.status == ReleaseStoreDeliveryStatus.STATUS_DELIVERED
        ):
            fuga_client.post_product_takedown(
                fuga_release.product_id, [fuga_spotify_store.external_id]
            )
            fuga_release.spotify_migration_completed_at = datetime.now()
            fuga_release.spotify_ready_to_migrate = False
            fuga_release.save()
            sleep(settings.FUGA_API_DELAY_IN_MS / 1000)


def fuga_migration_start(num_releases=100, wave=None):
    fuga_client = FugaAPIClient()
    fuga_releases = FugaMetadata.objects.filter(
        status='PUBLISHED',
        ready_to_migrate=True,
        spotify_migration_completed_at__isnull=False,
        migration_started_at__isnull=True,
        fuga_migration_wave__id=wave,
    )[:num_releases]
    for fuga_release in fuga_releases:
        sync_fuga_delivery_data([fuga_release])
        live_fuga_stores = ReleaseStoreDeliveryStatus.objects.filter(
            release_id=fuga_release.release_id,
            fuga_store__isnull=False,
            status=ReleaseStoreDeliveryStatus.STATUS_DELIVERED,
        )
        if not live_fuga_stores.exists():
            # At this point the fuga release should have been deleted from the sync
            continue

        # Find stores to redeliver
        fuga_store_ids = [
            live_fuga_store.fuga_store.external_id
            for live_fuga_store in live_fuga_stores
        ]
        direct_stores = Store.objects.filter(
            org_id__in=fuga_store_ids, admin_active=True
        )
        if direct_stores.exists():
            FugaMigrationReleaseStore.objects.filter(
                fuga_metadata=fuga_release
            ).delete()
            FugaMigrationReleaseStore.objects.bulk_create(
                [
                    FugaMigrationReleaseStore(
                        fuga_metadata=fuga_release,
                        release=fuga_release.release,
                        store=store,
                    )
                    for store in direct_stores
                ]
            )
            # Tag user on Zendesk with migration started
            fuga_release.release.user.fuga_migration = True
            fuga_release.release.user.save()
            try:
                zendesk.create_or_update_user(fuga_release.release.user.id)
            except Exception as exc:
                logger.exception(
                    'Failed to create or update Zendesk user %s',
                    fuga_release.release.user.id,
                )

            if fuga_client.delete_product(fuga_release.product_id):
                fuga_release.migration_started_at = datetime.now()
                fuga_release.save()
                sleep(settings.FUGA_API_DELAY_IN_MS / 1000)
        else:
            perform_fuga_delete(fuga_release)


def fuga_migration_direct_deliver(num_releases=100, wave=None, user_id=None):
    user = User.objects.get(id=user_id) if user_id else None  # Define when scheduled
    fuga_releases = FugaMetadata.objects.filter(
        migration_started_at__lte=datetime.now() - timedelta(hours=1),
        migration_completed_at__isnull=True,
        fuga_migration_wave__id=wave,
    )[:num_releases]
    for fuga_release in fuga_releases:
        stores = FugaMigrationReleaseStore.objects.filter(fuga_metadata=fuga_release)
        if stores.exists():
            store_internal_names = [store.store.internal_name for store in stores]
            if (
                "instagram" in store_internal_names
                and "facebook" in store_internal_names
            ):
                store_internal_names.remove("instagram")
            try:
                deliver_batches(
                    releases=[fuga_release.release],
                    delivery_type='insert',
                    stores=store_internal_names,
                    user=user,
                )
                fuga_release.status = 'MIGRATED'
                fuga_release.migration_completed_at = datetime.now()
                fuga_release.save()
            except Exception:
                fuga_release.status = 'UNDER_MIGRATION_ERROR'
                fuga_release.save()
            else:
                sync_fuga_delivery_data([fuga_release])
        else:
            fuga_release.status = 'UNDER_MIGRATION_NO_DIRECT_STORES'
            fuga_release.save()
