from amuse.services.delivery.checks.delivery_check import DeliveryCheck
from users.models import User


class LicensedCheck(DeliveryCheck):
    failure_message = (
        'Prevented because the release potentially contains amuse licensed content'
    )

    def passing(self) -> bool:
        if (
            self.operation == 'takedown'
            and self.release.user.category == User.CATEGORY_PRIORITY
        ):
            return False
        return True
