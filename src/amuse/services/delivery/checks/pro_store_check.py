from amuse.services.delivery.checks.delivery_check import DeliveryCheck

from users.models import User


class ProStoreCheck(DeliveryCheck):
    failure_message = (
        'Operation denied due to release owner not having a Pro or Plus account'
    )

    def passing(self) -> bool:
        if self.store.is_pro:
            return self.release.user.tier != User.TIER_FREE
        return True
