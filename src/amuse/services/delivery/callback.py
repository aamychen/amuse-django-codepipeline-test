from collections import defaultdict

from django.utils import timezone
from amuse.deliveries import CHANNELS
from amuse.models.deliveries import Batch, BatchDelivery, BatchDeliveryRelease
from amuse.services.delivery.helpers import get_taken_down_release_ids
from amuse.vendor.fuga.fuga_api import FugaAPIClient
from releases.models import Release, Store
from amuse.analytics import (
    segment_release_taken_down,
    segment_release_delivered,
    segment_release_undeliverable,
)
from amuse.tasks import smart_links_takedown
from releases.models.fuga_metadata import FugaMetadata
from releases.models.release_store_delivery_status import ReleaseStoreDeliveryStatus

BATCH_STATUS_MAP = dict(map(reversed, Batch.STATUS_OPTIONS.items()))
BATCH_DELIVERY_STATUS_MAP = dict(map(reversed, BatchDelivery.STATUS_OPTIONS.items()))
BATCH_DELIVERY_RELEASE_STATUS_MAP = dict(
    map(reversed, BatchDeliveryRelease.STATUS_OPTIONS.items())
)
BATCH_DELIVERY_RELEASE_DELIVERY_TYPE_MAP = dict(
    map(reversed, BatchDeliveryRelease.DELIVERY_TYPE_OPTIONS.items())
)
CHANNEL_MAP = dict(map(reversed, CHANNELS.items()))

BATCH_STATUS_MAP["delivered"] = Batch.STATUS_SUCCEEDED
BATCH_DELIVERY_STATUS_MAP["delivered"] = BatchDelivery.STATUS_SUCCEEDED
BATCH_DELIVERY_RELEASE_STATUS_MAP["delivered"] = BatchDeliveryRelease.STATUS_SUCCEEDED
RELEASE_STATUS_MAP = {
    'delivered': Release.STATUS_DELIVERED,
    'failed': Release.STATUS_UNDELIVERABLE,
}
BATCH_DELIVERY_RELEASE_TYPE_TO_RELEASE_DELIVERY_STATUS_MAP = {
    BatchDeliveryRelease.DELIVERY_TYPE_INSERT: ReleaseStoreDeliveryStatus.STATUS_DELIVERED,
    BatchDeliveryRelease.DELIVERY_TYPE_TAKEDOWN: ReleaseStoreDeliveryStatus.STATUS_TAKEDOWN,
    BatchDeliveryRelease.DELIVERY_TYPE_PRO_TAKEDOWN: ReleaseStoreDeliveryStatus.STATUS_TAKEDOWN,
}


def handler(message):
    if message["type"] == "batch_update":
        batch_update_handler(message)
    elif message["type"] == "delivery_created":
        delivery_created_handler(message)
    elif message["type"] == "delivery_update":
        delivery_update_handler(message)


def batch_update_handler(message):
    batch = Batch.objects.get(pk=message["batch_id"])
    batch.status = BATCH_STATUS_MAP[message["status"]]
    batch.save()


def delivery_created_handler(message):
    batch = Batch.objects.get(pk=message["batch_id"])
    delivery = BatchDelivery.objects.create(
        delivery_id=message["delivery_id"],
        channel=CHANNEL_MAP[message["channel"]],
        batch=batch,
    )
    for release_id, release_data in message["releases"].items():
        release = Release.objects.get(pk=int(release_id))
        batch_delivery_release = BatchDeliveryRelease.objects.create(
            delivery=delivery,
            release=release,
            type=BATCH_DELIVERY_RELEASE_DELIVERY_TYPE_MAP[
                release_data["delivery_type"]
            ],
        )
        release_stores = release.stores.all()
        excluded_stores = Store.objects.exclude(
            id__in=release_stores.values_list("id", flat=True)
        )
        batch_delivery_release.stores.set(release_stores)
        batch_delivery_release.excluded_stores.set(excluded_stores)

        if release_data.get("is_redelivery_for_bdr"):
            old_bdr_id = release_data["is_redelivery_for_bdr"]
            old_delivery = BatchDeliveryRelease.objects.get(id=old_bdr_id)
            old_delivery.redeliveries.add(batch_delivery_release)


def delivery_update_handler(message):
    delivery = BatchDelivery.objects.get(delivery_id=message["delivery_id"])
    delivery.status = BATCH_DELIVERY_STATUS_MAP[message["status"]]
    delivery.save()
    for release_id, release_data in message["releases"].items():
        delivery_release = BatchDeliveryRelease.objects.get(
            delivery=delivery, release__pk=release_id
        )
        delivery_release.status = BATCH_DELIVERY_RELEASE_STATUS_MAP[
            release_data["status"]
        ]
        if release_data["errors"]:
            delivery_release.errors = release_data["errors"]
        delivery_release.save()

        _update_release_store_delivery_status(delivery_release)

    _update_release_status(message["releases"].keys(), message['status'])


def _update_release_store_delivery_status(delivery_release):
    if (
        delivery_release.status == BatchDeliveryRelease.STATUS_SUCCEEDED
        and delivery_release.type
        in [
            BatchDeliveryRelease.DELIVERY_TYPE_INSERT,
            BatchDeliveryRelease.DELIVERY_TYPE_TAKEDOWN,
            BatchDeliveryRelease.DELIVERY_TYPE_PRO_TAKEDOWN,
        ]
    ):
        store_internal_name = CHANNELS[delivery_release.delivery.channel]

        if store_internal_name == "fuga":
            # Skip creating release store delivery status entries for FUGA
            return

        store = Store.objects.get(internal_name=store_internal_name)
        defaults = {
            "status": BATCH_DELIVERY_RELEASE_TYPE_TO_RELEASE_DELIVERY_STATUS_MAP[
                delivery_release.type
            ],
            "latest_delivery_log": delivery_release,
            "delivered_at": timezone.now(),
        }

        ReleaseStoreDeliveryStatus.objects.update_or_create(
            release_id=delivery_release.release.id, store=store, defaults=defaults
        )

        if store_internal_name == "twitch":
            # Handle Twitch/Amazon bundling, deliveries to Twitch always include Amazon
            ReleaseStoreDeliveryStatus.objects.update_or_create(
                release_id=delivery_release.release.id,
                store=Store.objects.get(internal_name="amazon"),
                defaults=defaults,
            )

        if store_internal_name == "facebook":
            # Handle Facebook/Instagram bundling, deliveries to Facebook always include Instagram
            ReleaseStoreDeliveryStatus.objects.update_or_create(
                release_id=delivery_release.release.id,
                store=Store.objects.get(internal_name="instagram"),
                defaults=defaults,
            )


def _update_release_status(release_ids, status):
    status_list = [
        Release.STATUS_APPROVED,
        Release.STATUS_UNDELIVERABLE,
        Release.STATUS_TAKEDOWN,
    ]
    release_status = RELEASE_STATUS_MAP.get(status)
    releases = Release.objects.filter(pk__in=release_ids)
    takedown_release_ids = []

    if release_status:
        if status == "delivered":
            takedown_release_ids = get_taken_down_release_ids(release_ids)
            releases_to_takedown = releases.filter(id__in=takedown_release_ids).exclude(
                status=Release.STATUS_TAKEDOWN
            )

            smart_links_takedown.delay(takedown_release_ids)
            for release in releases_to_takedown:
                segment_release_taken_down(release)

                # If release has a fuga id delete product from fuga
                fuga_medata = FugaMetadata.objects.filter(release=release).first()
                if fuga_medata and fuga_medata.product_id:
                    fuga_api_client = FugaAPIClient()
                    fuga_api_client.delete_product(fuga_medata.product_id)

            releases_to_takedown.update(status=Release.STATUS_TAKEDOWN)

        releases.exclude(id__in=takedown_release_ids).filter(
            status__in=status_list
        ).update(status=release_status)

        updated_releases = releases.exclude(id__in=takedown_release_ids).filter(
            status=release_status
        )

        if release_status == Release.STATUS_DELIVERED:
            for release in updated_releases:
                segment_release_delivered(release)
        elif release_status == Release.STATUS_UNDELIVERABLE:
            for release in updated_releases:
                segment_release_undeliverable(release)
