import base64
from json import JSONDecodeError
from urllib.parse import urlencode

import requests
from django.conf import settings
from django.core.signing import Signer
from django.urls import reverse


AUTHORIZE_URL = 'https://accounts.spotify.com/authorize?%s'
INVITE_URL = 'https://creator.wg.spotify.com/s4a-onboarding/v0/external/request'
SEARCH_URL = 'https://api.spotify.com/v1/search'
TOKEN_URL = 'https://accounts.spotify.com/api/token'


class SpotifyException(Exception):
    def __init__(self, response):
        try:
            response_data = response.json()
        except JSONDecodeError:
            response_data = response.text
        self.status_code = response.status_code
        self.message = 'Spotify API Error. HTTP status code: %s. Response: %s' % (
            response.status_code,
            response_data,
        )


def _build_basic_header() -> dict:
    auth = f'{settings.S4A_API_CLIENT_ID}:{settings.S4A_API_CLIENT_SECRET}'
    return {'Authorization': 'Basic ' + base64.b64encode(auth.encode()).decode()}


def _build_bearer_header(token) -> dict:
    return {'Authorization': 'Bearer ' + token}


def _get_bearer_token() -> str:
    payload = {'grant_type': 'client_credentials'}
    response = requests.post(TOKEN_URL, payload, headers=_build_basic_header())
    if response.status_code == 200:
        return response.json()['access_token']
    else:
        raise SpotifyException(response)


def build_state(user_id: int, artist_id: int) -> str:
    return Signer().sign(f'{user_id};{artist_id}')


def parse_state(state: str) -> tuple:
    user_id, artist_id = Signer().unsign(state).split(';')
    return int(user_id), int(artist_id)


def build_authorize_url(user_id: int, artist_id: int) -> str:
    """Returns URL to redirect user to, user will login to Spotify and
    from there grant the Amuse app access to his/her data.
    """
    redirect_url = settings.API_URL.rstrip("/") + reverse(
        'spotify-for-artists-callback'
    )
    authorize_params = urlencode(
        {
            'client_id': settings.S4A_API_CLIENT_ID,
            'redirect_uri': redirect_url,
            'response_type': 'code',
            'state': build_state(user_id, artist_id),
        }
    )
    return AUTHORIZE_URL % authorize_params


def create_access_token(user_id: int, artist_id: int, code: str) -> str:
    payload = {
        'code': code,
        'grant_type': 'authorization_code',
        'redirect_uri': settings.API_URL.rstrip("/")
        + reverse('spotify-for-artists-callback'),
    }
    response = requests.post(TOKEN_URL, payload, headers=_build_basic_header())
    if response.status_code == 200:
        return response.json()['access_token']
    else:
        raise SpotifyException(response)


def create_invite_url(access_token: str, artist_uri: str, release_uri: str) -> str:
    payload = {
        'albumUris': [release_uri],
        'artistUri': artist_uri,
        'clientSecret': settings.S4A_INVITE_CLIENT_SECRET,
    }
    response = requests.post(
        INVITE_URL, json=payload, headers=_build_bearer_header(access_token)
    )
    if response.status_code in (200, 201):
        return response.json()['url']
    else:
        raise SpotifyException(response)


def get_artist_spotify_id_and_release_uri(upc: str) -> tuple:
    headers = _build_bearer_header(_get_bearer_token())
    payload = {'q': f'upc:{upc}', 'type': 'album'}
    response = requests.get(SEARCH_URL, payload, headers=headers)
    if response.status_code == 200:
        data = response.json()
        try:
            artist_spotify_id = data['albums']['items'][0]['artists'][0]['id']
            release_uri = data['albums']['items'][0]['uri']
        except (KeyError, IndexError):
            return None, None
        return artist_spotify_id, release_uri
    else:
        raise SpotifyException(response)
