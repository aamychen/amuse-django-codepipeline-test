from json import loads

from django.conf import settings
from rauth.session import OAuth1Session

from amuse.settings.constants import AUDIOMACK_ARTIST_URL
from amuse.vendor.audiomack.audiomack_oauth_api import AudiomackOauthAPI


class AudiomackAPI:
    """
    API to get authenticated resources for the user from Audiomack once
    the user has gone through the oauth process already and we have
    the user's access token for that user.
    """

    def __init__(self, access_token, access_token_secret):
        self.service = AudiomackOauthAPI().client
        self.access_token = access_token
        self.access_token_secret = access_token_secret
        self.session = None

    def open_session(self):
        if not self.session:
            self.session = OAuth1Session(
                consumer_key=settings.AUDIOMACK_CONSUMER_KEY,
                consumer_secret=settings.AUDIOMACK_CONSUMER_SECRET,
                access_token=self.access_token,
                access_token_secret=self.access_token_secret,
                signature=None,
                service=self.service,
            )

    def close_session(self):
        if self.session:
            self.session.close()
        self.session = None

    def get_artist_info(self, artist_id):
        self.open_session()
        return self.session.get(url='artist-info/{}'.format(artist_id))

    def get_artist_slug(self):
        self.open_session()
        response = self.session.get(url='user')
        user_object = loads(response.content)
        return user_object["url_slug"]

    def get_artist_profile_url(self):
        user_slug = self.get_artist_slug()
        return AUDIOMACK_ARTIST_URL.format(user_slug) if user_slug else None
