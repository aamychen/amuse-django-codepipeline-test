from amuse.services.delivery.checks.delivery_check import DeliveryCheck
from releases.models import ReleaseStoreDeliveryStatus, Store


class YoutubeCIDLiveOnYouTubeCheck(DeliveryCheck):
    failure_message = (
        'Prevented insert because the release is not live on Youtube Music'
    )

    def passing(self) -> bool:
        if self.operation == 'insert':
            youtube_music_store = Store.objects.get(internal_name='youtube_music')
            return ReleaseStoreDeliveryStatus.objects.filter(
                release=self.release,
                store=youtube_music_store,
                status=ReleaseStoreDeliveryStatus.STATUS_DELIVERED,
            ).exists()
        return True
