from django.conf import settings
from rauth import OAuth1Service
from rauth.utils import parse_utf8_qsl


class AudiomackOauthAPI:
    """
    Oauth API for Audiomack that helps with the oauth flow in order to get the
    access token and artist id of the user. Once we have that then the
    AudiomackAPI can be used to access user resources from Audiomack.
    """

    def __init__(self):
        self.client = OAuth1Service(
            consumer_key=settings.AUDIOMACK_CONSUMER_KEY,
            consumer_secret=settings.AUDIOMACK_CONSUMER_SECRET,
            name='audiomack',
            access_token_url='https://api.audiomack.com/v1/access_token',
            authorize_url='https://www.audiomack.com/oauth/authenticate',
            request_token_url='https://api.audiomack.com/v1/request_token',
            base_url='https://api.audiomack.com/v1/',
        )

    def get_request_token(self, platform=None):
        request_token, request_token_secret = self.client.get_request_token(
            method='POST',
            data={
                'oauth_callback': f"{settings.AUDIOMACK_CALLBACK_API}?platform={platform}"
            },
        )
        return request_token, request_token_secret

    def get_authorize_url(self, request_token):
        authorize_url = self.client.get_authorize_url(request_token)
        return authorize_url

    def get_access_token_and_artist_id(
        self, request_token, request_token_secret, oauth_verifier
    ):
        response = self.client.get_raw_access_token(
            request_token,
            request_token_secret,
            method='POST',
            data={'oauth_verifier': oauth_verifier},
        )
        if response.status_code != 200:
            return None
        return parse_utf8_qsl(response.content)
