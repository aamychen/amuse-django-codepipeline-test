from amuse.services.delivery.checks.delivery_check import DeliveryCheck


class FFWDUserCheck(DeliveryCheck):
    failure_message = 'Prevented because the user has other releases with a FFWD deal'

    def passing(self) -> bool:
        if self.operation == 'takedown':
            return not self.release.user.has_locked_splits()
        return True
