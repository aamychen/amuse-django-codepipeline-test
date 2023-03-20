from unittest import mock

from django.test import TestCase
from rauth import OAuth1Session

from amuse.vendor.audiomack.audiomack_api import AudiomackAPI


_MOCKED_ARTIST_ID = 46528256


_MOCKED_RESPONSE = {
    "results": {
        "id": _MOCKED_ARTIST_ID,
        "name": "default",
        "image": "https://assets.audiomack.com/default-artist-image.png",
        "image_small": "https://assets.audiomack.com/default-artist-image.png?width=140&height=140&max=true",
        "image_medium": "https://assets.audiomack.com/default-artist-image.png?width=280&height=280&max=true",
        "image_large": "https://assets.audiomack.com/default-artist-image.png?width=1500&height=1500&max=true",
    }
}


class MockResponse:
    def __init__(self, status_code, content):
        self.status_code = status_code
        self.content = content


class TestAudiomackAPI(TestCase):
    def setUp(self):
        self.access_token = (
            '0920980c91df0af5deb41cfc6e87b11f090cfd6efd2586bfad2746ee54271270'
        )
        self.access_token_secret = (
            'fb5bc4aaec12cf90e49d12b05e256f91f6d18124e5b7b66575f02a5118920c32'
        )
        self.artist_id = _MOCKED_ARTIST_ID
        self.api = AudiomackAPI(self.access_token, self.access_token_secret)

    @mock.patch.object(
        OAuth1Session, 'get', return_value=MockResponse(200, _MOCKED_RESPONSE)
    )
    def test_get_artist_info(self, mock):
        artist_info_response = self.api.get_artist_info(artist_id=self.artist_id)
        self.assertEqual(artist_info_response.status_code, 200)
        self.assertDictEqual(
            artist_info_response.content["results"], _MOCKED_RESPONSE["results"]
        )
