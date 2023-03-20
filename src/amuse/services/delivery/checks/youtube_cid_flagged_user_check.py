from amuse.services.delivery.checks.delivery_check import DeliveryCheck
from releases.models import Song
from users.models import User


class YoutubeCIDFlaggedUserCheck(DeliveryCheck):
    failure_message = 'Prevented insert because the user is flagged'

    def passing(self) -> bool:
        if self.operation == 'insert':
            return self.release.user.category != User.CATEGORY_FLAGGED
        return True
