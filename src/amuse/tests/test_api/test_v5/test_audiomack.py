from unittest.mock import patch

from django.conf import settings

from django.urls import reverse
import pytest
from rauth import OAuth1Service
from rest_framework.exceptions import PermissionDenied

from amuse.api.base.views.audiomack import _set_cache
from amuse.api.base.views.exceptions import WrongAPIversionError
from amuse.platform import PlatformType
from amuse.tests.test_api.base import (
    API_V4_ACCEPT_VALUE,
    API_V5_ACCEPT_VALUE,
    AmuseAPITestCase,
)
from users.tests.factories import UserFactory

_MOCKED_REQUEST_TOKEN = (
    '316ec30e41153d1d42fbbd3f64d6fef4be8cae51bbd5e5fcf6b53fd9677566a6',
    'cd6a4610030d0509220426f3da3856b33b673bc84937a5012b08fc71118518c6',
)

_MOCKED_OAUTH_VERIFIER = (
    '36b97bdda2792fae6997864bbcf73ef5797b3c2c6013039a933b70b28c7cbad5'
)

_MOCKED_RESPONSE_CONTEXT = b'oauth_token=e76f13bb016dd5f5678a681fa032e89440444c7e41c8fae7b64ca26734de9a95&oauth_token_secret=6e78961441e0deac2ba0ce21f4405f91651dae9b307214599726ddeda6d453a9&artist_id=46528256'

_EXPECTED_RESPONSE = {
    'oauth_token': 'e76f13bb016dd5f5678a681fa032e89440444c7e41c8fae7b64ca26734de9a95',
    'oauth_token_secret': '6e78961441e0deac2ba0ce21f4405f91651dae9b307214599726ddeda6d453a9',
    'artist_id': '46528256',
}

_OAUTH_URL = 'https://www.audiomack.com/oauth/authenticate?oauth_token=foo'

_OAUTH_RESPONSE = {'url': _OAUTH_URL}


WEB_SUCCESS = f"{settings.WRB_URL}#/studio/artist?audiomack_oauth_flow=success"
WEB_FAILURE = f"{settings.WRB_URL}#/studio/artist?audiomack_oauth_flow=failed"

APP_SUCCESS = "com.amuseio://audiomack?audiomack_oauth_flow=success"
APP_FAILURE = "com.amuseio://audiomack?audiomack_oauth_flow=failed"


class MockResponse:
    def __init__(self, status_code, content):
        self.status_code = status_code
        self.content = content


class AudiomackOauthViewTestCase(AmuseAPITestCase):
    @patch('amuse.tasks.zendesk_create_or_update_user')
    def setUp(self, mock_zendesk):
        super().setUp()
        self.url = reverse('audiomack-oauth')
        self.user = UserFactory()
        self.artist = self.user.create_artist_v2('Mad Skillz')
        self.client.force_authenticate(self.user)
        self.client.credentials(HTTP_ACCEPT=API_V5_ACCEPT_VALUE)

    def test_wrong_api_version_return_400(self):
        self.client.credentials(HTTP_ACCEPT=API_V4_ACCEPT_VALUE)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 400)
        self.assertDictEqual(
            response.json(), {'detail': WrongAPIversionError.default_detail}
        )

    def test_logged_out_user(self):
        self.client.logout()

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 401)

    @patch.object(
        OAuth1Service, 'get_request_token', return_value=_MOCKED_REQUEST_TOKEN
    )
    @patch.object(OAuth1Service, 'get_authorize_url', return_value=_OAUTH_URL)
    def test_get_audiomack_oauth(self, *mocks):
        response = self.client.get(self.url, {'artist_id': self.artist.pk})

        self.assertEqual(response.status_code, 200)
        self.assertDictEqual(response.json(), _OAUTH_RESPONSE)

    @patch('amuse.tasks.zendesk_create_or_update_user')
    def test_get_audiomack_oauth_url_artist_not_authorized(self, mock_zendesk):
        # You should not be able to claim an artist you don't own
        malicious_user = UserFactory()
        self.user.create_artist_v2('Hacker Skillz')
        self.client.force_authenticate(malicious_user)

        response = self.client.get(self.url, {'artist_id': self.artist.pk})

        self.assertEqual(response.status_code, 403)
        self.assertDictEqual(
            response.json(), {'detail': PermissionDenied.default_detail}
        )

    def test_get_audiomack_oauth_url_artist_not_found(self):
        non_existing_artist_id = 123456789
        response = self.client.get(self.url, {'artist_id': non_existing_artist_id})

        self.assertEqual(response.status_code, 404)
        self.assertDictEqual(response.json(), {'detail': 'Artist not found'})

    def test_delete_audiomack_oauth(self):
        self.artist.audiomack_id = "1"
        self.artist.audiomack_access_token = "token"
        self.artist.audiomack_access_token_secret = "secret"
        self.artist.save()

        response = self.client.delete(self.url, {'artist_id': self.artist.pk})
        self.assertEqual(response.status_code, 204)
        self.assertFalse(response.content)

        self.artist.refresh_from_db()

        # We keep the audiomack artist id for tracking past releases
        self.assertEqual(self.artist.audiomack_id, "1")
        self.assertIsNone(self.artist.audiomack_access_token)
        self.assertIsNone(self.artist.audiomack_access_token_secret)


class AudiomackCallbackViewTestCase(AmuseAPITestCase):
    @patch('amuse.tasks.zendesk_create_or_update_user')
    def setUp(self, mock_zendesk):
        super().setUp()
        self.url = reverse('audiomack-callback')
        self.user = UserFactory()
        self.artist = self.user.create_artist_v2('Mad Skillz')

    @patch.object(
        OAuth1Service,
        'get_raw_access_token',
        return_value=MockResponse(200, _MOCKED_RESPONSE_CONTEXT),
    )
    def test_get_audiomack_callback_with_oauth_token_found(self, *mocks):
        _set_cache(*_MOCKED_REQUEST_TOKEN, self.user.pk, self.artist.pk)

        for platform_type in PlatformType:
            response = self.client.get(
                self.url,
                {
                    'oauth_token': _MOCKED_REQUEST_TOKEN[0],
                    'oauth_verifier': _MOCKED_OAUTH_VERIFIER,
                    'platform': platform_type.value,
                },
            )
            self.assertEqual(response.status_code, 302)
            expected_redirect_url = (
                APP_SUCCESS
                if platform_type in [PlatformType.IOS, PlatformType.ANDROID]
                else WEB_SUCCESS
            )
            self.assertEqual(response.url, expected_redirect_url)

            self.artist.refresh_from_db()
            self.assertEqual(self.artist.audiomack_id, _EXPECTED_RESPONSE['artist_id'])
            self.assertEqual(
                self.artist.audiomack_access_token, _EXPECTED_RESPONSE['oauth_token']
            )
            self.assertEqual(
                self.artist.audiomack_access_token_secret,
                _EXPECTED_RESPONSE['oauth_token_secret'],
            )

    def test_get_audiomack_callback_with_oauth_token_missing(self, *mocks):
        for platform_type in PlatformType:
            response = self.client.get(
                self.url,
                {
                    'oauth_token': 'non-existing-token',
                    'oauth_verifier': 'non-existing-verifier',
                    'platform': platform_type.value,
                },
            )

            self.assertEqual(response.status_code, 302)
            expected_redirect_url = (
                APP_FAILURE
                if platform_type in [PlatformType.IOS, PlatformType.ANDROID]
                else WEB_FAILURE
            )
            self.assertEqual(response.url, expected_redirect_url)
