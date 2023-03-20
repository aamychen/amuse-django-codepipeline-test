from amuse.services.delivery.checks.delivery_check import DeliveryCheck
from releases.models import ReleaseStoreDeliveryStatus


class FugaCheck(DeliveryCheck):
    failure_message = 'Operation denied due to Fuga controlled store for this release'

    def passing(self) -> bool:
        if self.store.fuga_store and ReleaseStoreDeliveryStatus.objects.filter(
            release=self.release,
            fuga_store=self.store.fuga_store,
            status=ReleaseStoreDeliveryStatus.STATUS_DELIVERED,
        ):
            return False
        return True
