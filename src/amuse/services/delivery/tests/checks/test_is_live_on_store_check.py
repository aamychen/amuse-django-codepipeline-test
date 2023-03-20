import responses
from django.test import TestCase, override_settings

from amuse.services.delivery.checks import IsLiveOnStoreCheck
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
class TestIsLiveOnStoreCheck(TestCase):
    @responses.activate
    def setUp(self):
        add_zendesk_mock_post_response()
        self.release = generate_releases(1, Release.STATUS_APPROVED)[0]
        self.spotify_store = StoreFactory(name='Spotify', internal_name='spotify')
        self.release.stores.add(self.spotify_store)

    def test_check_passing_for_insert(self):
        check = IsLiveOnStoreCheck(
            release=self.release, store=self.spotify_store, operation='insert'
        )
        self.assertTrue(check.passing())

    def test_check_not_passing_takedown(self):
        check = IsLiveOnStoreCheck(
            release=self.release, store=self.spotify_store, operation='takedown'
        )
        self.assertFalse(check.passing())

    def test_check_not_passing_update(self):
        check = IsLiveOnStoreCheck(
            release=self.release, store=self.spotify_store, operation='update'
        )
        self.assertFalse(check.passing())

    def test_check_passing_takedown(self):
        ReleaseStoreDeliveryStatusFactory(
            release=self.release,
            store=self.spotify_store,
            status=ReleaseStoreDeliveryStatus.STATUS_DELIVERED,
        )
        check = IsLiveOnStoreCheck(
            release=self.release, store=self.spotify_store, operation='takedown'
        )
        self.assertTrue(check.passing())

    def test_check_passing_update(self):
        ReleaseStoreDeliveryStatusFactory(
            release=self.release,
            store=self.spotify_store,
            status=ReleaseStoreDeliveryStatus.STATUS_DELIVERED,
        )
        check = IsLiveOnStoreCheck(
            release=self.release, store=self.spotify_store, operation='update'
        )
        self.assertTrue(check.passing())
