from decimal import Decimal

import responses
from django.test import TestCase, override_settings

from amuse.services.delivery.checks.ffwd_user_check import FFWDUserCheck
from amuse.tests.helpers import (
    add_zendesk_mock_post_response,
    ZENDESK_MOCK_API_URL_TOKEN,
)
from releases.models import Release, RoyaltySplit
from releases.tests.factories import (
    StoreFactory,
    generate_releases,
    RoyaltySplitFactory,
)


@override_settings(**ZENDESK_MOCK_API_URL_TOKEN)
class TestFFWDUserCheck(TestCase):
    @responses.activate
    def setUp(self):
        add_zendesk_mock_post_response()
        self.release = generate_releases(1, Release.STATUS_APPROVED)[0]
        self.song = self.release.songs.first()
        RoyaltySplitFactory(song=self.song, user=self.release.user, rate=Decimal('1'))
        self.spotify_store = StoreFactory(name='Spotify', internal_name='spotify')
        self.release.stores.add(self.spotify_store)

    def test_check_passing(self):
        check = FFWDUserCheck(
            release=self.release, store=self.spotify_store, operation='takedown'
        )
        self.assertTrue(check.passing())

    def test_check_not_passing(self):
        rs = RoyaltySplit.objects.filter(song=self.song, user=self.release.user).first()
        rs.is_locked = True
        rs.save()
        check = FFWDUserCheck(
            release=self.release, store=self.spotify_store, operation='takedown'
        )
        self.assertFalse(check.passing())
