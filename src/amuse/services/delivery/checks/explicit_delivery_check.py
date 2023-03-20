from amuse.services.delivery.checks.delivery_check import DeliveryCheck
from releases.models import Song


class ExplicitReleaseCheck(DeliveryCheck):
    failure_message = 'Prevented because the release contains an explicit track'

    def passing(self) -> bool:
        return not any(
            s.explicit == Song.EXPLICIT_TRUE for s in self.release.songs.all()
        )
