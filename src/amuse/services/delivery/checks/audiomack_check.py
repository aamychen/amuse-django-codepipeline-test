from amuse.services.delivery.checks.delivery_check import DeliveryCheck


class AudiomackCheck(DeliveryCheck):
    failure_message = (
        'Prevented because main primary artist on release does not have an audiomack_id'
    )

    def passing(self) -> bool:
        return True if self.release.main_primary_artist.audiomack_id else False
