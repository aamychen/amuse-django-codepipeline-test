from amuse.services.delivery.checks.delivery_check import DeliveryCheck


class FFWDReleaseCheck(DeliveryCheck):
    failure_message = 'Prevented because the release contains a FFWD deal'

    def passing(self) -> bool:
        if self.operation == 'takedown':
            return not self.release.has_locked_splits()
        return True
