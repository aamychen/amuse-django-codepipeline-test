from unittest.mock import patch

from django.urls import reverse
import responses
from rest_framework.exceptions import PermissionDenied

from amuse.tests.test_api.base import (
    API_V4_ACCEPT_VALUE,
    API_V5_ACCEPT_VALUE,
    AmuseAPITestCase,
)
from amuse.vendor.spotify.artists import (
    AUTHORIZE_URL,
    INVITE_URL,
    SEARCH_URL,
    TOKEN_URL,
    build_state,
)
from releases.models import Release
from releases.tests.factories import (
    ReleaseArtistRoleFactory,
    ReleaseFactory,
    StoreFactory,
)
from users.tests.factories import UserFactory

APPLICATION_TOKEN_RESPONSE = {
    'access_token': 'blahonga',
    'token_type': 'Bearer',
    'scope': '',
    'expires_in': 3600,
}
INVITE_RESPONSE = {
    'url': 'https://artists.spotify.com/c/distributor/invite/ed2a1ddd-93ad-49f4-bf3e-8da5a7528bb8?source=yourname&name=your%20name%20encoded&redirect_url=https%3A%2F%2Fyoururlencoded.com'
}
USER_TOKEN_RESPONSE = {
    'access_token': 'NgCXRK...MzYjw',
    'token_type': 'Bearer',
    'scope': '',
    'expires_in': 3600,
    'refresh_token': 'NgAagA...Um_SHo',
}
SEARCH_RESPONSE = {
    'albums': {
        'href': 'https://api.spotify.com/v1/search?query=upc%3A0616293984851&type=album&offset=0&limit=20',
        'items': [
            {
                'album_type': 'single',
                'artists': [
                    {
                        'external_urls': {
                            'spotify': 'https://open.spotify.com/artist/4hTTTrffOeBZo8NmcZJ5Zj'
                        },
                        'href': 'https://api.spotify.com/v1/artists/4hTTTrffOeBZo8NmcZJ5Zj',
                        'id': '4hTTTrffOeBZo8NmcZJ5Zj',
                        'name': 'artist name',
                        'type': 'artist',
                        'uri': 'spotify:artist:4hTTTrffOeBZo8NmcZJ5Zj',
                    }
                ],
                'available_markets': ['SE'],
                'external_urls': {
                    'spotify': 'https://open.spotify.com/album/3zHIB4QJk9uX8UYDTxM0yM'
                },
                'href': 'https://api.spotify.com/v1/albums/3zHIB4QJk9uX8UYDTxM0yM',
                'id': '3zHIB4QJk9uX8UYDTxM0yM',
                'images': [
                    {
                        'height': 640,
                        'url': 'https://i.scdn.co/image/ab67616d0000b27327f593a06d3f648552d618c6',
                        'width': 640,
                    },
                    {
                        'height': 300,
                        'url': 'https://i.scdn.co/image/ab67616d00001e0227f593a06d3f648552d618c6',
                        'width': 300,
                    },
                    {
                        'height': 64,
                        'url': 'https://i.scdn.co/image/ab67616d0000485127f593a06d3f648552d618c6',
                        'width': 64,
                    },
                ],
                'name': 'CODEINE',
                'release_date': '2020-12-02',
                'release_date_precision': 'day',
                'total_tracks': 1,
                'type': 'album',
                'uri': 'spotify:album:3zHIB4QJk9uX8UYDTxM0yM',
            }
        ],
        'limit': 20,
        'next': None,
        'offset': 0,
        'previous': None,
        'total': 1,
    }
}


class SpotifyForArtistsViewTestCase(AmuseAPITestCase):
    @patch('amuse.tasks.zendesk_create_or_update_user')
    def setUp(self, mock_zendesk):
        super().setUp()

        self.url = reverse('spotify-for-artists')
        self.user = UserFactory()
        self.artist = self.user.create_artist_v2('skadabadabadeee pa pa pa da pop')
        self.release = ReleaseFactory(
            status=Release.STATUS_RELEASED,
            upc__code='A0616293984851',
            stores=[StoreFactory(name='Spotify', active=True)],
        )
        ReleaseArtistRoleFactory(release=self.release, artist=self.artist)

        self.client.force_authenticate(self.user)
        self.client.credentials(HTTP_ACCEPT=API_V5_ACCEPT_VALUE)

    def test_wrong_api_version_return_400(self):
        self.client.credentials(HTTP_ACCEPT=API_V4_ACCEPT_VALUE)

        response = self.client.get(self.url)

        assert response.status_code == 400
        assert response.json() == {'detail': 'API version is not supported.'}

    def test_logged_out_user(self):
        self.client.logout()

        response = self.client.get(self.url)

        assert response.status_code == 401

    @responses.activate
    def test_get_redirect_url_valid_artist_id_redirects_to_spotify_auth(self):
        responses.add(responses.POST, TOKEN_URL, json=USER_TOKEN_RESPONSE)
        responses.add(responses.POST, TOKEN_URL, json=APPLICATION_TOKEN_RESPONSE)
        responses.add(responses.GET, SEARCH_URL, json=SEARCH_RESPONSE)

        response = self.client.get(self.url, {'artist_id': self.artist.pk}, follow=True)

        assert response.status_code == 200
        assert response.json()['url'].startswith(AUTHORIZE_URL % '')

    @patch('amuse.tasks.zendesk_create_or_update_user')
    def test_get_redirect_url_unowned_artist_id_returns_400(self, mock_zendesk):
        # You should not be able to claim an artist you don't own
        user_without_artist = UserFactory()
        self.client.force_authenticate(user_without_artist)

        response = self.client.get(self.url, {'artist_id': self.artist.pk})

        assert response.status_code == 400
        assert response.json() == {'artist_id': ['Invalid artist']}

    def test_get_redirect_url_connected_artist_redirects_to_s4a(self):
        expected_redirect_url = 'https://example.com'
        self.artist.spotify_id = 'example.com'
        self.artist.spotify_for_artists_url = expected_redirect_url
        self.artist.save()

        response = self.client.get(self.url, {'artist_id': self.artist.pk}, follow=True)

        assert response.status_code == 200
        assert response.json()['url'] == expected_redirect_url


class SpotifyForArtistsCallbackViewTestCase(AmuseAPITestCase):
    @patch('amuse.tasks.zendesk_create_or_update_user')
    def setUp(self, mock_zendesk):
        super().setUp()

        self.url = reverse('spotify-for-artists-callback')
        self.user = UserFactory()
        self.artist = self.user.create_artist_v2('skadabadabadeee pa pa pa da pop')
        self.store = StoreFactory(name='Spotify', active=True)
        self.release = ReleaseFactory(
            status=Release.STATUS_RELEASED,
            stores=[self.store],
            upc__code='A0616293984851',
        )
        ReleaseArtistRoleFactory(release=self.release, artist=self.artist)
        self.payload = {
            'state': build_state(self.user.pk, self.artist.pk),
            'code': 'access token',
        }

    @responses.activate
    @patch('amuse.api.v5.serializers.spotify_for_artists.s4a_connected')
    def test_artist_does_not_exist_returns_400(self, mock_analytics):
        self.payload['state'] = build_state(self.user.pk, self.artist.pk + 1)
        response = self.client.get(self.url, self.payload, follow=True)

        assert response.status_code == 400
        assert response.json() == {'non_field_errors': ['Invalid artist']}
        assert mock_analytics.call_count == 0

    @responses.activate
    @patch('amuse.api.v5.serializers.spotify_for_artists.s4a_connected')
    def test_successful_callback_redirects_to_s4a_invite(self, mock_analytics):
        responses.add(responses.POST, TOKEN_URL, json=USER_TOKEN_RESPONSE)
        responses.add(responses.POST, TOKEN_URL, json=APPLICATION_TOKEN_RESPONSE)
        responses.add(responses.GET, SEARCH_URL, json=SEARCH_RESPONSE)
        responses.add(responses.POST, INVITE_URL, json=INVITE_RESPONSE, status=201)

        response = self.client.get(self.url, self.payload, follow=True)
        redirect_url, status_code = response.redirect_chain[0]
        self.artist.refresh_from_db()

        assert len(response.redirect_chain) == 1
        assert status_code == 302
        assert redirect_url == INVITE_RESPONSE['url']
        assert (
            self.artist.spotify_id
            == SEARCH_RESPONSE['albums']['items'][0]['artists'][0]['id']
        )
        assert self.artist.spotify_for_artists_url == INVITE_RESPONSE['url']
        mock_analytics.assert_called_once_with(self.user.pk, self.artist.pk)

    @responses.activate
    @patch('amuse.api.v5.serializers.spotify_for_artists.logger.info')
    @patch('amuse.api.v5.serializers.spotify_for_artists.s4a_connected')
    def test_create_access_token_error_returns_400(self, mock_analytics, mock_logger):
        responses.add(responses.POST, TOKEN_URL, json={}, status=500)

        response = self.client.get(self.url, self.payload)

        assert response.status_code == 400
        assert response.json() == {'non_field_errors': ['500']}
        mock_logger.assert_called_once()
        assert mock_analytics.call_count == 0

    @responses.activate
    @patch('amuse.api.v5.serializers.spotify_for_artists.logger.info')
    @patch('amuse.api.v5.serializers.spotify_for_artists.s4a_connected')
    def test_create_invite_url_error_returns_400(self, mock_analytics, mock_logger):
        responses.add(responses.POST, TOKEN_URL, json=USER_TOKEN_RESPONSE)
        responses.add(responses.POST, TOKEN_URL, json=APPLICATION_TOKEN_RESPONSE)
        responses.add(responses.GET, SEARCH_URL, json=SEARCH_RESPONSE)
        responses.add(responses.POST, INVITE_URL, json={}, status=500)

        response = self.client.get(self.url, self.payload)

        assert response.status_code == 400
        assert response.json() == {'non_field_errors': ['500']}
        assert mock_analytics.call_count == 0
        mock_logger.assert_called_once()

    @responses.activate
    @patch('amuse.api.v5.serializers.spotify_for_artists.logger.info')
    @patch('amuse.api.v5.serializers.spotify_for_artists.s4a_connected')
    def test_search_url_error_returns_400(self, mock_analytics, mock_logger):
        responses.add(responses.POST, TOKEN_URL, json=USER_TOKEN_RESPONSE)
        responses.add(responses.POST, TOKEN_URL, json=APPLICATION_TOKEN_RESPONSE)
        responses.add(responses.GET, SEARCH_URL, json={}, status=500)

        response = self.client.get(self.url, self.payload)

        assert response.status_code == 400
        assert response.json() == {'non_field_errors': ['500']}
        assert mock_analytics.call_count == 0
        mock_logger.assert_called_once()

    @responses.activate
    @patch('amuse.api.v5.serializers.spotify_for_artists.s4a_connected')
    def test_artist_has_no_release_on_spotify_returns_400(self, mock_analytics):
        responses.add(responses.POST, TOKEN_URL, json=USER_TOKEN_RESPONSE)
        responses.add(responses.POST, TOKEN_URL, json=APPLICATION_TOKEN_RESPONSE)
        responses.add(responses.GET, SEARCH_URL, json={})

        response = self.client.get(self.url, self.payload)

        assert response.status_code == 400
        assert response.json() == {'artist_id': ['Artist has no release on Spotify']}
        assert mock_analytics.call_count == 0

    @patch('amuse.api.v5.serializers.spotify_for_artists.s4a_connected')
    def test_artist_has_excluded_spotify_from_all_releases_returns_400(
        self, mock_analytics
    ):
        self.release.stores.remove(self.store)
        response = self.client.get(self.url, self.payload)

        assert response.status_code == 400
        assert response.json() == {'artist_id': ['Artist has no release on Spotify']}
        assert mock_analytics.call_count == 0

    @responses.activate
    @patch('amuse.api.v5.serializers.spotify_for_artists.s4a_connected')
    def test_forged_state_returns_400(self, mock_analytics):
        response = self.client.get(self.url, {'state': 'h4x0r', 'code': 'h4x'})

        assert response.status_code == 400
        assert response.json() == {'state': ['Invalid state']}
        assert mock_analytics.call_count == 0


class SpotifyForArtistsDisconnectViewTestCase(AmuseAPITestCase):
    @patch('amuse.tasks.zendesk_create_or_update_user')
    def setUp(self, mock_zendesk):
        super().setUp()
        self.url = reverse('spotify-for-artists-disconnect')
        self.user = UserFactory()
        self.artist = self.user.create_artist_v2('Happy Kidz')
        self.client.force_authenticate(self.user)
        self.client.credentials()

    def test_logged_out_user(self):
        self.client.logout()
        response = self.client.delete(self.url, {'artist_id': self.artist.pk})
        self.assertEqual(response.status_code, 401)

    @patch('amuse.tasks.zendesk_create_or_update_user')
    def test_disconnect_artist_not_authorized(self, mock_zendesk):
        # You should not be able to disconnect an artist you don't own
        malicious_user = UserFactory()
        self.user.create_artist_v2('Happy Kidz')
        self.client.force_authenticate(malicious_user)

        response = self.client.delete(self.url, {'artist_id': self.artist.pk})

        self.assertEqual(response.status_code, 403)
        self.assertDictEqual(
            response.json(), {'detail': PermissionDenied.default_detail}
        )

    def test_disconnect_artist_not_found(self):
        non_existing_artist_id = 123456789
        response = self.client.delete(self.url, {'artist_id': non_existing_artist_id})

        self.assertEqual(response.status_code, 404)
        self.assertDictEqual(response.json(), {'detail': 'Artist not found'})

    def test_disconnect(self):
        self.artist.spotify_id = "123"
        self.artist.spotify_for_artists_url = "'https://artists.url"
        self.artist.save()

        response = self.client.delete(self.url, {'artist_id': self.artist.pk})
        self.assertEqual(response.status_code, 204)
        self.assertFalse(response.content)

        self.artist.refresh_from_db()

        # We keep the spotify artist id for tracking past releases
        self.assertEqual(self.artist.spotify_id, "123")
        self.assertIsNone(self.artist.spotify_for_artists_url)
