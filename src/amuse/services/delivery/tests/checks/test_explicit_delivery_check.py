import responses
from django.test import TestCase, override_settings

from amuse.services.delivery.checks import ExplicitReleaseCheck
from amuse.tests.helpers import (
    ZENDESK_MOCK_API_URL_TOKEN,
    add_zendesk_mock_post_response,
)
from releases.models import Release, Song
from releases.tests.factories import StoreFactory, generate_releases


@override_settings(**ZENDESK_MOCK_API_URL_TOKEN)
class TestExplicitReleaseCheck(TestCase):
    @responses.activate
    def setUp(self):
        add_zendesk_mock_post_response()
        self.release = generate_releases(1, Release.STATUS_APPROVED)[0]
        self.tencent_store = StoreFactory(name='Tencent', internal_name='tencent')
        self.release.stores.add(self.tencent_store)

    def test_check_passing(self):
        check = ExplicitReleaseCheck(
            release=self.release, store=self.tencent_store, operation='insert'
        )
        self.assertTrue(check.passing())

    def test_check_not_passing(self):
        for song in self.release.songs.all():
            song.explicit = Song.EXPLICIT_TRUE
            song.save()
        check = ExplicitReleaseCheck(
            release=self.release, store=self.tencent_store, operation='insert'
        )
        self.assertFalse(check.passing())
