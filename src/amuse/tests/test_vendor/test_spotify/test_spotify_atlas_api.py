import json
import pathlib

import responses
from django.test import TestCase

from amuse.vendor.spotify.spotify_atlas_api import SpotifyAtlasAPI

absolute_src_path = pathlib.Path(__file__).parent.parent.resolve()


def load_fixture(filename):
    return open(f"{absolute_src_path}/fixtures/{filename}").read()


class SpotifyAtlasTestCase(TestCase):
    def setUp(self):
        self.client = SpotifyAtlasAPI()
        self.client.base_url = "https://unit-test.com/base-url/"
        self.client.sonar_base_url = "https://unit-test.com/sonar_base_url/"
        self.client.oauth_uri = "https://unit-test.com/oauth_uri"
        self.client.api_token_uri = "https://unit-test.com/api_token_uri"
        self.client.redirect_uri = "https://unit-test.com/redirect_uri"
        self.client.in_production = True
        self.client.access_token = None

    def test_extract_auth_code_from_html_response(self):
        html_text_response = load_fixture("SpotifyOauthResponse.html")
        code = self.client._extract_auth_code_from_html_response(html_text_response)
        self.assertEqual(code, "auth_code_to_extract")

    @responses.activate
    def test_get_auth_code(self):
        responses.add(
            responses.GET,
            self.client.oauth_uri,
            body=load_fixture("SpotifyOauthResponse.html"),
            status=200,
        )
        code = self.client._get_auth_code()
        self.assertEqual(code, "auth_code_to_extract")

    @responses.activate
    def test_get_auth_code_throws_error(self):
        responses.add(
            responses.GET,
            self.client.oauth_uri,
            json={"error": "Bad request"},
            status=400,
        )
        self.assertRaises(ConnectionError, self.client._get_auth_code)

    @responses.activate
    def test_get_access_token_from_auth_code(self):
        responses.add(
            responses.POST,
            self.client.api_token_uri,
            json=json.loads(load_fixture("SpotifyApiTokenResponse.json")),
            status=200,
        )
        access_token = self.client._get_access_token_from_auth_code("code")
        self.assertEqual(access_token, "access_token")

    @responses.activate
    def test_get_access_token_from_auth_code_throws_error(self):
        responses.add(
            responses.POST,
            self.client.api_token_uri,
            json={"error": "Bad request"},
            status=400,
        )
        self.assertRaises(
            ConnectionError, self.client._get_access_token_from_auth_code, "code"
        )

    @responses.activate
    def test_login(self):
        responses.add(
            responses.GET,
            self.client.oauth_uri,
            body=load_fixture("SpotifyOauthResponse.html"),
            status=200,
        )
        responses.add(
            responses.POST,
            self.client.api_token_uri,
            json=json.loads(load_fixture("SpotifyApiTokenResponse.json")),
            status=200,
        )
        self.assertIsNone(self.client.access_token)
        self.client._login()
        self.assertEqual(self.client.access_token, "access_token")

    @responses.activate
    def test_get_access_token(self):
        responses.add(
            responses.GET,
            self.client.oauth_uri,
            body=load_fixture("SpotifyOauthResponse.html"),
            status=200,
        )
        responses.add(
            responses.POST,
            self.client.api_token_uri,
            json=json.loads(load_fixture("SpotifyApiTokenResponse.json")),
            status=200,
        )
        self.assertIsNone(self.client.access_token)
        access_token = self.client._get_access_token()
        self.assertEqual(access_token, "access_token")

    @responses.activate
    def test_search_album_by_upc(self):
        upc = "7316111222333"
        responses.add(
            responses.GET,
            self.client.oauth_uri,
            body=load_fixture("SpotifyOauthResponse.html"),
            status=200,
        )
        responses.add(
            responses.POST,
            self.client.api_token_uri,
            json=json.loads(load_fixture("SpotifyApiTokenResponse.json")),
            status=200,
        )
        responses.add(
            responses.GET,
            self.client.base_url + "v3/search/album",
            json=json.loads(load_fixture("SpotifySearchAlbumByUPCResponse.json")),
            status=200,
        )
        self.assertIsNone(self.client.access_token)
        results = self.client.search_album_by_upc(upc)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["uri"], "spotify:album:album_id")

    @responses.activate
    def test_get_album(self):
        album_spotify_id = "spotify:album:album_id"
        responses.add(
            responses.GET,
            self.client.oauth_uri,
            body=load_fixture("SpotifyOauthResponse.html"),
            status=200,
        )
        responses.add(
            responses.POST,
            self.client.api_token_uri,
            json=json.loads(load_fixture("SpotifyApiTokenResponse.json")),
            status=200,
        )
        responses.add(
            responses.GET,
            "https://unit-test.com/base-url/v2/album/{}".format(album_spotify_id),
            json=json.loads(load_fixture("SpotifyGetAlbumResponse.json")),
            status=200,
        )
        album = self.client.get_album(album_spotify_id)
        self.assertEqual(album["effectiveData"]["name"], "album_name")
        self.assertEqual(album["effectiveData"]["uri"], album_spotify_id)
        self.assertEqual(
            album["effectiveData"]["url"], "https://open.spotify.com/album/album_id"
        )
        self.assertEqual(len(album["effectiveData"]["artists"]), 2)
        self.assertEqual(
            album["effectiveData"]["artists"][0]["uri"], "spotify:artist:artist_id1"
        )
        self.assertEqual(album["effectiveData"]["artists"][0]["role"], "main artist")
        self.assertEqual(
            album["effectiveData"]["artists"][1]["uri"], "spotify:artist:artist_id2"
        )
        self.assertEqual(album["effectiveData"]["artists"][1]["role"], "composer")
        self.assertEqual(len(album["effectiveData"]["tracks"]), 4)
        self.assertEqual(
            album["effectiveData"]["tracks"][0]["uri"], "spotify:track:track_id1"
        )
        self.assertEqual(album["effectiveData"]["tracks"][0]["isrc"], "SE62M1234567")

    @responses.activate
    def test_get_album_track(self):
        album_spotify_id = "spotify:album:album_id"
        track_spotify_id = "spotify:track:track_id1"
        responses.add(
            responses.GET,
            self.client.oauth_uri,
            body=load_fixture("SpotifyOauthResponse.html"),
            status=200,
        )
        responses.add(
            responses.POST,
            self.client.api_token_uri,
            json=json.loads(load_fixture("SpotifyApiTokenResponse.json")),
            status=200,
        )
        responses.add(
            responses.GET,
            "https://unit-test.com/base-url/v2/album/{}/track/{}".format(
                album_spotify_id, track_spotify_id
            ),
            json=json.loads(load_fixture("SpotifyGetAlbumTrackResponse.json")),
            status=200,
        )
        album = self.client.get_album_track(album_spotify_id, track_spotify_id)
        self.assertEqual(album["effectiveData"]["name"], "track_name")
        self.assertEqual(album["effectiveData"]["isrc"], "SE62M1234567")
        self.assertEqual(album["effectiveData"]["uri"], track_spotify_id)
        self.assertEqual(
            album["effectiveData"]["url"], "https://open.spotify.com/track/track_id1"
        )
        self.assertEqual(len(album["effectiveData"]["artists"]), 2)
        self.assertEqual(
            album["effectiveData"]["artists"][0]["uri"], "spotify:artist:artist_id1"
        )
        self.assertEqual(album["effectiveData"]["artists"][0]["role"], "main artist")
        self.assertEqual(
            album["effectiveData"]["artists"][1]["uri"], "spotify:artist:artist_id2"
        )
        self.assertEqual(album["effectiveData"]["artists"][1]["role"], "composer")
