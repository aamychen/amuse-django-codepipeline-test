import logging

from time import sleep

from datetime import datetime
from django.conf import settings

from amuse.analytics import segment_release_taken_down
from amuse.logging import logger
from amuse.tasks import smart_links_takedown
from amuse.vendor.fuga.fuga_api import FugaAPIClient, FugaNotFoundError
from releases.models import Release, ReleaseStoreDeliveryStatus
from releases.models.fuga_metadata import FugaDeliveryHistory, FugaStores


def sync_fuga_delivery_data(fuga_releases, delay=None):
    fuga_client = FugaAPIClient()
    delay = (settings.FUGA_API_DELAY_IN_MS if not delay else delay) / 1000

    for fuga_release in fuga_releases:
        start = datetime.now()
        logging.info(
            f"Fuga release sync started for release: {fuga_release.release_id}"
        )
        try:
            fuga_store_data = fuga_client.get_delivery_history(
                fuga_product_id=fuga_release.product_id
            )
        except FugaNotFoundError as e:
            fuga_release.status = 'PERMANENTLY_DELETED'
            fuga_release.mark_to_be_deleted = False
            fuga_release.delete_started_at = datetime.now()
            fuga_release.save()
            continue
        fuga_release.last_synced_at = datetime.now()
        # if stores differ from that in database perform fuga stores sync
        if _fuga_stores_delivery_status_mismatch(fuga_release, fuga_store_data):
            # Sync delivery status of all fuga stores returned by fuga api call
            for fuga_external_store_id in fuga_store_data.keys():
                fuga_store = FugaStores.objects.filter(
                    external_id=fuga_external_store_id
                ).first()

                if not fuga_store:
                    logging.warning(
                        f"Skipping fuga store data sync as no FugaStores object was found matching external_id: {fuga_external_store_id}, release: {fuga_release.release_id}"
                    )
                    continue

                records = fuga_client.get_delivery_history_for_dsp(
                    fuga_release.product_id, fuga_external_store_id
                )
                FugaDeliveryHistory.sync_records_from_fuga(
                    fuga_release, fuga_store, records
                )
            fuga_release.delivery_history_extracted_at = fuga_release.last_synced_at
        fuga_release.save()
        if fuga_release.status != 'MIGRATED':
            sync_fuga_release_status(fuga_client, fuga_release)
        check_if_release_is_now_takendown(fuga_release.release)
        time_diff = datetime.now() - start
        logging.info(
            f"Fuga release sync completed for release: {fuga_release.release_id}, runtime in ms: {time_diff.total_seconds()* 1000}"
        )
        sleep(delay)


def _fuga_stores_delivery_status_mismatch(fuga_release, fuga_store_data):
    fuga_delivered_store_ids = [
        fuga_store_id
        for fuga_store_id in fuga_store_data.keys()
        if fuga_store_data[fuga_store_id]['state'] == 'DELIVERED'
        and fuga_store_data[fuga_store_id]['action'] != 'TAKEDOWN'
    ]

    release_store_delivery_statuses = ReleaseStoreDeliveryStatus.objects.filter(
        release_id=fuga_release.release_id,
        fuga_store__isnull=False,
        status=ReleaseStoreDeliveryStatus.STATUS_DELIVERED,
    )

    db_delivered_fuga_store_ids = [
        rsds.fuga_store.external_id for rsds in release_store_delivery_statuses
    ]

    return set(fuga_delivered_store_ids) != set(db_delivered_fuga_store_ids)


def sync_fuga_release_status(fuga_client, fuga_release):
    fuga_live_stores = ReleaseStoreDeliveryStatus.objects.filter(
        release=fuga_release.release_id,
        status=ReleaseStoreDeliveryStatus.STATUS_DELIVERED,
        fuga_store__isnull=False,
    )
    if fuga_live_stores.count() in (1, 2, 3):
        if all(
            fuga_live_store.fuga_store.name
            in ["iMusica", "YouTube Music (legacy)", "Napster"]
            for fuga_live_store in fuga_live_stores
        ):
            for fuga_live_store in fuga_live_stores:
                fuga_live_store.status = ReleaseStoreDeliveryStatus.STATUS_TAKEDOWN
                fuga_live_store.latest_fuga_delivery_log = None
                fuga_live_store.delivered_at = datetime.now()
                fuga_live_store.save()
    if fuga_release.status == 'PUBLISHED':
        fuga_live_stores = fuga_live_stores.all()
        if not fuga_release.delete_started_at and not fuga_live_stores.exists():
            if fuga_client.delete_product(fuga_product_id=fuga_release.product_id):
                fuga_release.mark_to_be_deleted = False
                fuga_release.delete_started_at = datetime.now()
                fuga_release.save()
        elif fuga_client.get_product_status(fuga_release.product_id) == 'DELETED':
            fuga_release.status = 'DELETED'
            fuga_release.save()
        elif fuga_release.release.status in [
            Release.STATUS_TAKEDOWN,
            Release.STATUS_DELETED,
        ]:
            fuga_release.mark_to_be_deleted = True
            fuga_release.save()


def check_if_release_is_now_takendown(release):
    if not ReleaseStoreDeliveryStatus.objects.filter(
        release=release.id, status=ReleaseStoreDeliveryStatus.STATUS_DELIVERED
    ).exists() and release.status in [
        Release.STATUS_DELIVERED,
        Release.STATUS_RELEASED,
    ]:
        release.status = Release.STATUS_TAKEDOWN
        release.save()

        segment_release_taken_down(release)
        smart_links_takedown.delay([release.id])


def perform_fuga_delete(fuga_release):
    client = FugaAPIClient()
    if client.delete_product(fuga_product_id=fuga_release.product_id):
        fuga_release.mark_to_be_deleted = False
        fuga_release.delete_started_at = datetime.now()
        fuga_release.save()
    else:
        logger.warning(f"Could not delete fuga product {str(fuga_release.product_id)}")
