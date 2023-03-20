from amuse.services.delivery.checks.delivery_check import DeliveryCheck


class FrozenUserCheck(DeliveryCheck):
    failure_message = 'Prevented because the user/release owner has been frozen'

    def passing(self) -> bool:
        if self.operation in ['insert', 'update']:
            return not self.release.user.is_frozen
        return True
