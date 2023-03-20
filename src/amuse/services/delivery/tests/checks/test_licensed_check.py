from unittest.mock import patch

import responses
from django.test import TestCase, override_settings

from amuse.services.delivery.checks import LicensedCheck
from amuse.tests.helpers import (
    add_zendesk_mock_post_response,
    ZENDESK_MOCK_API_URL_TOKEN,
)
from releases.models import Release
from releases.tests.factories import StoreFactory, generate_releases
from releases.tests.test_release_model import ReleaseTestCase
from users.models import User


@override_settings(**ZENDESK_MOCK_API_URL_TOKEN)
class TestLicensedCheck(TestCase):
    @responses.activate
    def setUp(self):
        add_zendesk_mock_post_response()
        self.release = generate_releases(1, Release.STATUS_APPROVED)[0]
        self.song = self.release.songs.first()
        self.spotify_store = StoreFactory(name='Spotify', internal_name='spotify')
        self.release.stores.add(self.spotify_store)

    @patch(
        'releases.models.release.get_release_with_license_info',
        return_value=ReleaseTestCase.RELEASE_WITHOUT_LICENSE_INFO,
    )
    def test_check_passing(self, mock_response):
        check = LicensedCheck(
            release=self.release, store=self.spotify_store, operation='takedown'
        )
        self.assertTrue(check.passing())

    @patch(
        'releases.models.release.get_release_with_license_info',
        return_value=ReleaseTestCase.RELEASE_WITH_LICENSE_INFO,
    )
    def test_check_not_passing(self, mocked_has_licensed_tracks):
        self.release.user.category = User.CATEGORY_PRIORITY
        self.release.user.save()
        check = LicensedCheck(
            release=self.release, store=self.spotify_store, operation='takedown'
        )
        self.assertFalse(check.passing())
