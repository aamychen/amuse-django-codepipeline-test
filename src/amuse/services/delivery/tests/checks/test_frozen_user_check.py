import responses
from django.test import TestCase, override_settings

from amuse.services.delivery.checks.frozen_user_check import FrozenUserCheck
from amuse.tests.helpers import (
    add_zendesk_mock_post_response,
    ZENDESK_MOCK_API_URL_TOKEN,
)
from releases.models import Release
from releases.tests.factories import StoreFactory, generate_releases


@override_settings(**ZENDESK_MOCK_API_URL_TOKEN)
class TestFFWDUserCheck(TestCase):
    @responses.activate
    def setUp(self):
        add_zendesk_mock_post_response()
        self.release = generate_releases(1, Release.STATUS_APPROVED)[0]
        self.spotify_store = StoreFactory(name='Spotify', internal_name='spotify')
        self.release.stores.add(self.spotify_store)

    def test_check_passing(self):
        check = FrozenUserCheck(
            release=self.release, store=self.spotify_store, operation='insert'
        )
        self.assertTrue(check.passing())

    def test_check_not_passing(self):
        user = self.release.user
        user.is_frozen = True
        user.save()
        check = FrozenUserCheck(
            release=self.release, store=self.spotify_store, operation='insert'
        )
        self.assertFalse(check.passing())
