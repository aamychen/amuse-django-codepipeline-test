import logging
from datetime import datetime, timedelta

import requests
from django.conf import settings
from base64 import standard_b64encode as b64encode

AMUSE_LINKS_URL = 'https://api.amu.se/api/saveAlbum'
AMUSE_BASE_LINK = 'https://amu.se/share/album/'

logger = logging.getLogger(__name__)


class SpotifyAPI:
    def __init__(self):
        self.spotify_auth_token = None
        self.expires = None

    def fetch_spotify_bearer_token(self):
        expired = datetime.now() >= self.expires if self.expires else True
        if self.spotify_auth_token and not expired:
            return self.spotify_auth_token

        basic_token = b64encode(
            f'{settings.SPOTIFY_API_CLIENT_ID}:{settings.SPOTIFY_API_CLIENT_SECRET}'.encode(
                'ascii'
            )
        ).decode('ascii')
        headers = {'Authorization': f'Basic {basic_token}'}
        data = {'grant_type': 'client_credentials'}
        r = requests.post(
            'https://accounts.spotify.com/api/token', headers=headers, data=data
        )
        data = r.json()
        self.spotify_auth_token = data.get('access_token')
        self.expires = datetime.now() + timedelta(seconds=data.get('expires_in'))
        return self.spotify_auth_token

    def fetch_spotify_album_by_upc(self, upc):
        access_token = self.fetch_spotify_bearer_token()
        headers = {'Authorization': f'Bearer {access_token}'}
        params = {'q': f'upc:{upc}', 'type': 'album'}
        r = requests.get(
            'https://api.spotify.com/v1/search', headers=headers, params=params
        )
        if r.status_code != 200:
            content = r.content.decode('utf8')
            logger.error(
                'Could not find album with upc %s with status code %s and content %s',
                upc.code,
                r.status_code,
                content,
            )
            return None
        items = r.json().get('albums').get('items')
        if not items:
            logger.info('Could not find album with upc %s', upc.code)
            return None
        return items[0]

    def fetch_spotify_link(self, upc):
        album = self.fetch_spotify_album_by_upc(upc)
        if not album:
            return None
        return album.get('external_urls').get('spotify')

    def fetch_spotify_artist(self, spotify_id):
        access_token = self.fetch_spotify_bearer_token()
        headers = {'Authorization': f'Bearer {access_token}'}
        r = requests.get(
            f'https://api.spotify.com/v1/artists/{spotify_id}', headers=headers
        )
        if r.status_code != 200:
            content = r.content.decode('utf8')
            logger.warning(
                'Could not find artist with id %s with status code %s and content %s',
                spotify_id,
                r.status_code,
                content,
            )
            return None

        return r.json()

    def fetch_spotify_artist_image_url(self, spotify_id):
        if not spotify_id:
            return None

        artist = self.fetch_spotify_artist(spotify_id)
        if not artist:
            return None

        images = artist.get('images')
        return images[0]['url'] if images else None
