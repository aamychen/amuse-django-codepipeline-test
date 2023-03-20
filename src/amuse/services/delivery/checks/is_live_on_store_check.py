from amuse.services.delivery.checks.delivery_check import DeliveryCheck
from releases.models import ReleaseStoreDeliveryStatus


class IsLiveOnStoreCheck(DeliveryCheck):
    failure_message = (
        'Prevented operation since release is not live on DSP according to Jarvis'
    )

    def passing(self) -> bool:
        if self.operation in ['update', 'takedown']:
            return ReleaseStoreDeliveryStatus.objects.filter(
                release=self.release,
                store=self.store,
                status=ReleaseStoreDeliveryStatus.STATUS_DELIVERED,
            ).exists()
        return True
