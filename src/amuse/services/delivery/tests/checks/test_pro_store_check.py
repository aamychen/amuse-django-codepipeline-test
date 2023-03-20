import responses
from django.test import TestCase, override_settings

from amuse.services.delivery.checks import ProStoreCheck
from amuse.tests.helpers import (
    ZENDESK_MOCK_API_URL_TOKEN,
    add_zendesk_mock_post_response,
)
from releases.models import Release
from releases.tests.factories import StoreFactory, generate_releases
from subscriptions.models import Subscription
from subscriptions.tests.factories import SubscriptionPlanFactory, SubscriptionFactory


@override_settings(**ZENDESK_MOCK_API_URL_TOKEN)
class TestProStoreCheck(TestCase):
    @responses.activate
    def setUp(self):
        add_zendesk_mock_post_response()
        self.release = generate_releases(1, Release.STATUS_APPROVED)[0]
        self.spotify_store = StoreFactory(
            name='Spotify', internal_name='spotify', is_pro=False
        )
        self.tiktok_store = StoreFactory(
            name='Tiktok', internal_name='tiktok', is_pro=True
        )
        self.release.stores.add(self.spotify_store)
        self.release.stores.add(self.tiktok_store)

    def test_check_passing_with_free_user_free_store(self):
        check = ProStoreCheck(
            release=self.release, store=self.spotify_store, operation='insert'
        )
        self.assertTrue(check.passing())

    def test_check_not_passing_with_free_user_pro_store(self):
        check = ProStoreCheck(
            release=self.release, store=self.tiktok_store, operation='insert'
        )
        self.assertFalse(check.passing())

    def test_check_passing_with_pro_user_free_store(self):
        SubscriptionFactory(
            plan=SubscriptionPlanFactory(trial_days=90, period=12),
            provider=Subscription.PROVIDER_ADYEN,
            user=self.release.user,
        )
        check = ProStoreCheck(
            release=self.release, store=self.spotify_store, operation='insert'
        )
        self.assertTrue(check.passing())

    def test_check_passing_with_pro_user_pro_store(self):
        SubscriptionFactory(
            plan=SubscriptionPlanFactory(trial_days=90, period=12),
            provider=Subscription.PROVIDER_ADYEN,
            user=self.release.user,
        )
        check = ProStoreCheck(
            release=self.release, store=self.tiktok_store, operation='insert'
        )
        self.assertTrue(check.passing())
