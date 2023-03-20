import responses
from django.test import TestCase, override_settings

from amuse.services.delivery.checks import YoutubeCIDLiveOnYouTubeCheck
from amuse.tests.helpers import (
    ZENDESK_MOCK_API_URL_TOKEN,
    add_zendesk_mock_post_response,
)
from releases.models import Release, ReleaseStoreDeliveryStatus
from releases.tests.factories import (
    StoreFactory,
    generate_releases,
    ReleaseStoreDeliveryStatusFactory,
)


@override_settings(**ZENDESK_MOCK_API_URL_TOKEN)
class TestYoutubeCIDLiveOnYouTubeCheck(TestCase):
    @responses.activate
    def setUp(self):
        add_zendesk_mock_post_response()
        self.release = generate_releases(1, Release.STATUS_APPROVED)[0]
        self.youtube_music_store = StoreFactory(
            name='Youtube Music', internal_name='youtube_music'
        )
        self.youtube_cid_store = StoreFactory(
            name='Youtube CID', internal_name='youtube_content_id'
        )
        self.release.stores.add(self.youtube_cid_store)

    def test_check_passing(self):
        ReleaseStoreDeliveryStatusFactory(
            release=self.release,
            store=self.youtube_music_store,
            status=ReleaseStoreDeliveryStatus.STATUS_DELIVERED,
        )

        check = YoutubeCIDLiveOnYouTubeCheck(
            release=self.release, store=self.youtube_cid_store, operation='insert'
        )
        self.assertTrue(check.passing())

    def test_check_not_passing_youtube_music_never_released(self):
        check = YoutubeCIDLiveOnYouTubeCheck(
            release=self.release, store=self.youtube_cid_store, operation='insert'
        )
        self.assertFalse(check.passing())

    def test_check_not_passing_youtube_music_takendown(self):
        ReleaseStoreDeliveryStatusFactory(
            release=self.release,
            store=self.youtube_music_store,
            status=ReleaseStoreDeliveryStatus.STATUS_TAKEDOWN,
        )
        check = YoutubeCIDLiveOnYouTubeCheck(
            release=self.release, store=self.youtube_cid_store, operation='insert'
        )
        self.assertFalse(check.passing())
