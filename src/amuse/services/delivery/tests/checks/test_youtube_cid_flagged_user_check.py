import responses
from django.test import TestCase, override_settings

from amuse.services.delivery.checks import YoutubeCIDFlaggedUserCheck
from amuse.tests.helpers import (
    ZENDESK_MOCK_API_URL_TOKEN,
    add_zendesk_mock_post_response,
)
from releases.models import Release
from releases.tests.factories import StoreFactory, generate_releases
from users.models import User


@override_settings(**ZENDESK_MOCK_API_URL_TOKEN)
class TestYoutubeCIDFlaggedUserCheck(TestCase):
    @responses.activate
    def setUp(self):
        add_zendesk_mock_post_response()
        self.release = generate_releases(1, Release.STATUS_APPROVED)[0]
        self.youtube_cid_store = StoreFactory(
            name='Youtube CID', internal_name='youtube_content_id'
        )
        self.release.stores.add(self.youtube_cid_store)

    def test_check_passing(self):
        check = YoutubeCIDFlaggedUserCheck(
            release=self.release, store=self.youtube_cid_store, operation='insert'
        )
        self.assertTrue(check.passing())

    def test_check_not_passing(self):
        user = self.release.user
        user.category = User.CATEGORY_FLAGGED
        user.save()
        check = YoutubeCIDFlaggedUserCheck(
            release=self.release, store=self.youtube_cid_store, operation='insert'
        )
        self.assertFalse(check.passing())
