import responses
from django.test import TestCase, override_settings

from amuse.services.delivery.checks import YoutubeCIDMonetizationCheck
from amuse.tests.helpers import (
    ZENDESK_MOCK_API_URL_TOKEN,
    add_zendesk_mock_post_response,
)
from releases.models import Release, Song
from releases.tests.factories import StoreFactory, generate_releases


@override_settings(**ZENDESK_MOCK_API_URL_TOKEN)
class TestYoutubeCIDMonetizationCheck(TestCase):
    @responses.activate
    def setUp(self):
        add_zendesk_mock_post_response()
        self.release = generate_releases(1, Release.STATUS_APPROVED)[0]
        self.youtube_cid_store = StoreFactory(
            name='Youtube CID', internal_name='youtube_content_id'
        )
        self.release.stores.add(self.youtube_cid_store)

    def test_check_passing(self):
        for song in self.release.songs.all():
            song.youtube_content_id = Song.YT_CONTENT_ID_MONETIZE
            song.save()
        check = YoutubeCIDMonetizationCheck(
            release=self.release, store=self.youtube_cid_store, operation='insert'
        )
        self.assertTrue(check.passing())

    def test_check_not_passing(self):
        check = YoutubeCIDMonetizationCheck(
            release=self.release, store=self.youtube_cid_store, operation='insert'
        )
        self.assertFalse(check.passing())
