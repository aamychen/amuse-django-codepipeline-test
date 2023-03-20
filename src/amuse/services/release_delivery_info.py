import logging

from amuse.deliveries import CHANNELS
from amuse.models.deliveries import BatchDeliveryRelease
from releases.models import Store, FugaDeliveryHistory, FugaStores
from releases.models.release_store_delivery_status import ReleaseStoreDeliveryStatus
from releases.utils import release_explicit

DISALLOW_EXPLICIT = ("tencent", "netease")
CHANNEL_MAP = dict(map(reversed, CHANNELS.items()))

logger = logging.getLogger(__name__)


class ReleaseDeliveryInfo:
    def __init__(self, release):
        self.release = release
        self.fuga_delivery_info = self._get_fuga_delivery_info()
        self.store_delivery_info = self._get_store_delivery_info()

    def get_direct_delivery_channels(self, method):
        delivery_channels = []

        if method == 'insert':
            delivery_channels = [
                info['channel_name']
                for info in self.store_delivery_info
                if info['deliver_to']
            ]

        elif method in ['takedown', 'update', 'full_update', 'metadata_update']:
            delivery_channels = [
                info['channel_name']
                for info in self.store_delivery_info
                if info['delivery_status']
                and info['delivery_status'].status
                == ReleaseStoreDeliveryStatus.STATUS_DELIVERED
            ]

        return self._handle_store_bundling(delivery_channels)

    def get_fuga_delivery_channels(self, method):
        if method in ['insert', 'update', 'metadata_update']:
            # We don't allow insert or metadata only updates to fuga
            return []

        elif method in ['full_update', 'takedown']:
            return [
                info['channel_name']
                for info in self.fuga_delivery_info
                if info['channel_name']
                and info['delivery_status']
                and info['delivery_status'].status
                == ReleaseStoreDeliveryStatus.STATUS_DELIVERED
            ]

    def _get_store_delivery_info(self):
        store_delivery_info = []
        all_stores = Store.objects.filter(admin_active=True).order_by(
            '-show_on_top', '-active', '-is_pro', 'name'
        )

        for store in all_stores:
            (
                include_store_in_delivery,
                excluded_reason,
            ) = self._include_store_in_delivery(store)

            channel = (
                CHANNEL_MAP[store.internal_name]
                if store.internal_name in CHANNEL_MAP.keys()
                else None
            )

            # Override channel mapping for instagram as always handled via facebook
            if store.internal_name == 'instagram':
                channel = CHANNEL_MAP['facebook']

            store_delivery_info.append(
                {
                    'store': store,
                    'channel_name': CHANNELS[channel] if channel else None,
                    'deliver_to': include_store_in_delivery,
                    'excluded_reason': excluded_reason,
                    'delivery_status': ReleaseStoreDeliveryStatus.objects.filter(
                        release=self.release, store=store
                    ).first(),
                    'last_delivery': BatchDeliveryRelease.objects.filter(
                        release=self.release, delivery__channel=channel
                    ).last(),
                }
            )

        return store_delivery_info

    def _get_fuga_delivery_info(self):
        fuga_delivery_info = []
        fuga_release_store_delivery_statuses = (
            ReleaseStoreDeliveryStatus.objects.filter(
                release=self.release, fuga_store__isnull=False
            )
        )

        for release_store_delivery_status in fuga_release_store_delivery_statuses:
            store = Store.objects.filter(
                fuga_store_id=release_store_delivery_status.fuga_store.id
            ).first()

            fuga_delivery_info.append(
                {
                    'store': store,
                    'name': release_store_delivery_status.fuga_store.name,
                    'channel_name': f'fuga_{store.internal_name}'
                    if store and store.fuga_store.has_delivery_service_support
                    else None,
                    'delivery_status': release_store_delivery_status,
                }
            )

        return fuga_delivery_info

    def _include_store_in_delivery(self, store):
        if store not in self.release.stores.all():
            return False, "Store not in selected release stores"

        # Bundled stores handling
        if (
            store.internal_name == "instagram"
            and "facebook" in self.release.included_internal_stores
        ):
            return False, "Instagram is handled via Facebook"

        if (
            store.internal_name == "amazon"
            and "twitch" in self.release.included_internal_stores
        ):
            return False, "Twitch deliveries always include Amazon"

        # Explicit stores check
        if (
            release_explicit(self.release) == "explicit"
            and store.internal_name in DISALLOW_EXPLICIT
        ):
            return False, f"{store.name} excluded as release is marked as explicit"

        # Check release is not currently live on store via fuga
        if store.id in [
            info['store'].id
            for info in self.fuga_delivery_info
            if info['delivery_status'].status
            == ReleaseStoreDeliveryStatus.STATUS_DELIVERED
            and info['store']
        ]:
            return (
                False,
                f"Cannot use direct feed as {store.name} is currently handled via fuga",
            )

        return True, None

    @staticmethod
    def _handle_store_bundling(delivery_channels):
        # If both amazon and twitch, we only require to trigger deliveries to twitch
        if 'amazon' in delivery_channels and 'twitch' in delivery_channels:
            delivery_channels.remove('amazon')

        # Remove duplicate elements, this happens when both instagram and facebook are included as they both use the facebook channel
        return list(set(delivery_channels))

    @staticmethod
    def has_been_live_on_fuga_store(release_id, fuga_store_external_id):
        """
        Returns true if the release has ever been live (past or present) on Fuga for
        the given Fuga store provided by fuga_store_id
        """
        records = FugaDeliveryHistory.objects.filter(
            release_id=release_id,
            fuga_store=FugaStores.objects.filter(
                external_id=fuga_store_external_id
            ).first(),
            action__in=["INSERT", "REDELIVERY"],
            state="DELIVERED",
        )
        return records.exists()
