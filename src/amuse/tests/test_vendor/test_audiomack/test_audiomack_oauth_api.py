from unittest import mock

from django.test import TestCase
from rauth import OAuth1Service

from amuse.vendor.audiomack.audiomack_oauth_api import AudiomackOauthAPI


class MockResponse:
    def __init__(self, status_code, content):
        self.status_code = status_code
        self.content = content


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


class TestAudiomackOauthAPI(TestCase):
    def setUp(self):
        self.api = AudiomackOauthAPI()

    @mock.patch.object(
        OAuth1Service, 'get_request_token', return_value=_MOCKED_REQUEST_TOKEN
    )
    def test_get_request_token(self, mock):
        request_token, request_token_secret = self.api.get_request_token()
        self.assertEqual(_MOCKED_REQUEST_TOKEN[0], request_token)
        self.assertEqual(_MOCKED_REQUEST_TOKEN[1], request_token_secret)

    def test_get_authorize_url(self):
        request_token = _MOCKED_REQUEST_TOKEN[0]
        authorize_url = self.api.get_authorize_url(request_token)
        self.assertEqual(
            authorize_url,
            '{}?oauth_token={}'.format(self.api.client.authorize_url, request_token),
        )

    @mock.patch.object(
        OAuth1Service,
        'get_raw_access_token',
        return_value=MockResponse(200, _MOCKED_RESPONSE_CONTEXT),
    )
    def test_get_access_token_and_artist_id(self, mock):
        response = self.api.get_access_token_and_artist_id(
            _MOCKED_REQUEST_TOKEN[0], _MOCKED_REQUEST_TOKEN[1], _MOCKED_OAUTH_VERIFIER
        )
        self.assertDictEqual(response, _EXPECTED_RESPONSE)

    @mock.patch.object(
        OAuth1Service,
        'get_raw_access_token',
        return_value=MockResponse(
            422, b'{"errorcode":1048,"message":"Verification code invalid"}'
        ),
    )
    def test_get_access_token_and_artist_id_with_wrong_verifier(self, mock):
        response = self.api.get_access_token_and_artist_id(
            _MOCKED_REQUEST_TOKEN[0], _MOCKED_REQUEST_TOKEN[1], 'wrong_verifier'
        )
        self.assertIsNone(response)
