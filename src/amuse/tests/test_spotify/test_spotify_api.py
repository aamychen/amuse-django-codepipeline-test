import pytest

from unittest import mock
from datetime import datetime, timedelta

from requests import Response
from django.test import override_settings

from amuse.vendor.spotify import SpotifyAPI
from codes.tests import factories


@mock.patch('amuse.vendor.spotify.spotify_api.SpotifyAPI.fetch_spotify_bearer_token')
@mock.patch('requests.get')
def test_fetch_spotify_artist(get_mock, bearer_token_mock):
    api = SpotifyAPI()
    bearer_token_mock.return_value = 'ACCESS_TOKEN'

    response = Response()
    response.status_code = 200
    content = b'{"id":"FAKE_SPOTIFY_ID"}'
    response._content = content
    get_mock.return_value = response

    artist = api.fetch_spotify_artist('FAKE_SPOTIFY_ID')
    headers = {'Authorization': 'Bearer ACCESS_TOKEN'}

    get_mock.assert_called_once_with(
        'https://api.spotify.com/v1/artists/FAKE_SPOTIFY_ID', headers=headers
    )
    bearer_token_mock.assert_called_once()
    assert artist.get('id') == 'FAKE_SPOTIFY_ID'


@mock.patch('amuse.vendor.spotify.spotify_api.SpotifyAPI.fetch_spotify_bearer_token')
@mock.patch('requests.get')
def test_fetch_spotify_artist_fails(get_mock, bearer_token_mock):
    api = SpotifyAPI()
    bearer_token_mock.return_value = 'ACCESS_TOKEN'

    response = Response()
    response.status_code = 400
    content = (
        b'{"error":"400 - {\"error\":{\"status\":400,\"message\":\"invalid id\"}}"}'
    )
    response._content = content
    get_mock.return_value = response

    artist = api.fetch_spotify_artist('FAKE_SPOTIFY_ID')
    headers = {'Authorization': 'Bearer ACCESS_TOKEN'}

    get_mock.assert_called_once_with(
        'https://api.spotify.com/v1/artists/FAKE_SPOTIFY_ID', headers=headers
    )
    bearer_token_mock.assert_called_once()
    assert artist is None


@mock.patch('amuse.vendor.spotify.spotify_api.SpotifyAPI.fetch_spotify_artist')
def test_fetch_spotify_artist_image_url(api_mock):
    api = SpotifyAPI()

    # missing spotify_id test
    image_url = api.fetch_spotify_artist_image_url(None)
    assert image_url is None

    # unable to find artist for specified spotify_id test
    api_mock.return_value = None
    image_url = api.fetch_spotify_artist_image_url('INVALID_SPOTIFY_ID')
    assert image_url is None

    # no image test
    api_mock.return_value = {'images': []}
    image_url = api.fetch_spotify_artist_image_url('INVALID_SPOTIFY_ID')
    assert image_url is None

    # valid response test
    api_mock.return_value = {"images": [{"url": "https://i.scdn.co/image/FAKE_IMAGE"}]}
    image_url = api.fetch_spotify_artist_image_url('FAKE_SPOTIFY_ID')
    assert image_url == 'https://i.scdn.co/image/FAKE_IMAGE'

    api_mock.assert_called()


@pytest.mark.parametrize(
    'fetch_album_by_upc_mock_response,expected',
    [
        (
            {'external_urls': {'spotify': 'https://mock-url.spotify.com'}},
            'https://mock-url.spotify.com',
        ),
        (None, None),
        ({'external_urls': {}}, None),
    ],
)
@mock.patch('amuse.vendor.spotify.spotify_api.SpotifyAPI.fetch_spotify_album_by_upc')
def test_fetch_spotify_link(
    fetch_album_by_upc_mock, fetch_album_by_upc_mock_response, expected
):
    api = SpotifyAPI()
    mock_upc = 'mock_upc'
    fetch_album_by_upc_mock.return_value = fetch_album_by_upc_mock_response
    result = api.fetch_spotify_link(mock_upc)
    fetch_album_by_upc_mock.assert_called_once_with(mock_upc)
    assert result == expected


def test_fetch_spotify_bearer_token_not_expired_has_token():
    api = SpotifyAPI()
    mock_token = 'mock-spotify-token'
    api.spotify_auth_token = mock_token
    api.expires = datetime.now() + timedelta(days=1)
    result = api.fetch_spotify_bearer_token()
    assert result == mock_token


@pytest.mark.parametrize(
    'auth_token_mock,auth_expires',
    [
        (None, None),
        (None, datetime.now() - timedelta(days=1)),
        ('mock-token', None),
        ('mock-token', datetime.now() - timedelta(days=1)),
        (None, datetime.now() + timedelta(days=1)),
    ],
)
@mock.patch('requests.post')
def test_fetch_spotify_bearer_token(post_mock, auth_token_mock, auth_expires):
    api = SpotifyAPI()
    expected = 'mock-spotify-token'
    api.spotify_auth_token = auth_token_mock
    api.expires = auth_expires
    basic_mock_token = (
        'bW9jay1zcG90aWZ5LWNsaWVudC1pZDptb2NrLXNwb3RpZnktY2xpZW50LXNlY3JldA=='
    )
    headers = {'Authorization': f'Basic {basic_mock_token}'}
    data = {'grant_type': 'client_credentials'}
    with override_settings(
        SPOTIFY_API_CLIENT_ID='mock-spotify-client-id',
        SPOTIFY_API_CLIENT_SECRET='mock-spotify-client-secret',
    ):
        response_mock = Response()
        response_mock.status_code = 200
        response_content = (
            b'{"access_token": "mock-spotify-token", "expires_in": 30000}'
        )
        response_mock._content = response_content
        post_mock.return_value = response_mock
        result = api.fetch_spotify_bearer_token()
        post_mock.assert_called_once_with(
            'https://accounts.spotify.com/api/token', headers=headers, data=data
        )
        assert result == expected


@mock.patch('amuse.vendor.spotify.spotify_api.SpotifyAPI.fetch_spotify_bearer_token')
@mock.patch('requests.get')
@pytest.mark.django_db
def test_fetch_spotify_album_by_upc_status_code_200(
    get_mock, fetch_spotify_bearer_token_mock
):
    api = SpotifyAPI()
    mock_bearer_token_mock = 'mock-token'
    mock_upc_code_value = 'mock-upc'
    mock_upc_code = factories.UPCFactory(code=mock_upc_code_value)
    fetch_spotify_bearer_token_mock.return_value = mock_bearer_token_mock
    mock_headers = {'Authorization': f'Bearer {mock_bearer_token_mock}'}
    mock_params = {'q': f'upc:{mock_upc_code_value}', 'type': 'album'}
    response_mock = Response()
    response_mock.status_code = 200
    response_content = b'{"albums": {"items": [{"id": "mock-album"}]}}'
    expected = {"id": "mock-album"}
    response_mock._content = response_content
    get_mock.return_value = response_mock
    result = api.fetch_spotify_album_by_upc(mock_upc_code)
    get_mock.assert_called_once_with(
        'https://api.spotify.com/v1/search', headers=mock_headers, params=mock_params
    )

    assert result == expected


@mock.patch('amuse.vendor.spotify.spotify_api.logger')
@mock.patch('amuse.vendor.spotify.spotify_api.SpotifyAPI.fetch_spotify_bearer_token')
@mock.patch('requests.get')
@pytest.mark.django_db
def test_fetch_spotify_album_by_upc_status_code_400(
    get_mock, fetch_spotify_bearer_token_mock, logger_mock
):
    api = SpotifyAPI()
    mock_bearer_token_mock = 'mock-token'
    mock_upc_code_value = 'mock-upc'
    mock_upc_code = factories.UPCFactory(code=mock_upc_code_value)
    fetch_spotify_bearer_token_mock.return_value = mock_bearer_token_mock
    mock_headers = {'Authorization': f'Bearer {mock_bearer_token_mock}'}
    mock_params = {'q': f'upc:{mock_upc_code_value}', 'type': 'album'}
    response_mock = Response()
    response_mock.status_code = 400
    response_content = b'{"error": "Failed fetching albums by upc"}'
    response_mock._content = response_content
    get_mock.return_value = response_mock
    result = api.fetch_spotify_album_by_upc(mock_upc_code)
    get_mock.assert_called_once_with(
        'https://api.spotify.com/v1/search', headers=mock_headers, params=mock_params
    )
    logger_mock.error.assert_called_once_with(
        'Could not find album with upc %s with status code %s and content %s',
        mock_upc_code_value,
        400,
        '{"error": "Failed fetching albums by upc"}',
    )
    assert result is None


@mock.patch('amuse.vendor.spotify.spotify_api.logger')
@mock.patch('amuse.vendor.spotify.spotify_api.SpotifyAPI.fetch_spotify_bearer_token')
@mock.patch('requests.get')
@pytest.mark.django_db
def test_fetch_spotify_album_by_upc_status_code_200_empty_response(
    get_mock, fetch_spotify_bearer_token_mock, logger_mock
):
    api = SpotifyAPI()
    mock_bearer_token_mock = 'mock-token'
    mock_upc_code_value = 'mock-upc'
    mock_upc_code = factories.UPCFactory(code=mock_upc_code_value)
    fetch_spotify_bearer_token_mock.return_value = mock_bearer_token_mock
    mock_headers = {'Authorization': f'Bearer {mock_bearer_token_mock}'}
    mock_params = {'q': f'upc:{mock_upc_code_value}', 'type': 'album'}
    response_mock = Response()
    response_mock.status_code = 200
    response_content = b'{"albums": {"items": []}}'
    response_mock._content = response_content
    get_mock.return_value = response_mock
    result = api.fetch_spotify_album_by_upc(mock_upc_code)
    get_mock.assert_called_once_with(
        'https://api.spotify.com/v1/search', headers=mock_headers, params=mock_params
    )
    logger_mock.info.assert_called_once_with(
        'Could not find album with upc %s', mock_upc_code_value
    )
    assert result is None
