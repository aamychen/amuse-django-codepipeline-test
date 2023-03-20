import responses
from django.test import TestCase, override_settings

from amuse.services.delivery.checks import AudiomackCheck
from amuse.tests.helpers import (
    ZENDESK_MOCK_API_URL_TOKEN,
    add_zendesk_mock_post_response,
)
from releases.models import Release
from releases.tests.factories import StoreFactory, generate_releases


@override_settings(**ZENDESK_MOCK_API_URL_TOKEN)
class TestAudiomackCheck(TestCase):
    @responses.activate
    def setUp(self):
        add_zendesk_mock_post_response()
        self.release = generate_releases(1, Release.STATUS_APPROVED)[0]
        self.audiomack_store = StoreFactory(name='Audiomack', internal_name='audiomack')
        self.release.stores.add(self.audiomack_store)

    def test_check_passing(self):
        artist = self.release.main_primary_artist
        artist.audiomack_id = 123
        artist.save()

        check = AudiomackCheck(
            release=self.release, store=self.audiomack_store, operation='insert'
        )
        self.assertTrue(check.passing())

    def test_check_not_passing(self):
        artist = self.release.main_primary_artist
        artist.audiomack_id = None
        artist.save()

        check = AudiomackCheck(
            release=self.release, store=self.audiomack_store, operation='insert'
        )
        self.assertFalse(check.passing())
