from amuse.services.delivery.checks.delivery_check import DeliveryCheck
from releases.models import Song


class YoutubeCIDMonetizationCheck(DeliveryCheck):
    failure_message = 'Prevented insert because the release has no monetized tracks'

    def passing(self) -> bool:
        if self.operation == 'insert':
            return any(
                s.youtube_content_id == Song.YT_CONTENT_ID_MONETIZE
                for s in self.release.songs.all()
            )
        return True
