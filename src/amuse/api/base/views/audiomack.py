import logging

from django.conf import settings
from django.core.cache import cache
from django.http import HttpResponseRedirect
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from amuse import mixins as logmixins
from amuse.api.base.mixins import ArtistAuthorizationMixin
from amuse.api.base.views.exceptions import WrongAPIversionError
from amuse.api.v5.serializers.audiomack import (
    AudiomackOauthSerializer,
    AudiomackCallbackSerializer,
)
from amuse.platform import PlatformHelper, PlatformType
from amuse.vendor.audiomack.audiomack_oauth_api import AudiomackOauthAPI

logger = logging.getLogger(__name__)

# Request tokens expire from audiomack after 1h
CACHE_FOR_HOURS = 1 * 60 * 60


def _set_cache(request_token, request_token_secret, user_id, artist_id):
    """
    Temporarily stores that the given Audiomack request_token is associated
    with the given user_id, artist_id and request_token_secret.
    """
    audiomack_key = 'audiomack/{}'.format(request_token)
    audiomack_value = {
        "user_id": user_id,
        "artist_id": artist_id,
        "request_token_secret": request_token_secret,
    }
    cache.set(audiomack_key, audiomack_value, CACHE_FOR_HOURS)


def _get_redirect_url(platform, success=None):
    suffix = "success" if success else "failed"
    if platform in [PlatformType.IOS, PlatformType.ANDROID]:
        redirect_url = f"com.amuseio://audiomack?audiomack_oauth_flow={suffix}"
    else:
        redirect_url = (
            f"{settings.WRB_URL}#/studio/artist?audiomack_oauth_flow={suffix}"
        )
    return redirect_url


class CustomAmuseHttpResponseRedirect(HttpResponseRedirect):
    allowed_schemes = ['http', 'https', 'ftp', 'com.amuseio']


class AudiomackOauthView(ArtistAuthorizationMixin, logmixins.LogMixin, APIView):
    permission_classes = [IsAuthenticated]

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        if self.request.version != '5':
            raise WrongAPIversionError()

    def get(self, request, *args, **kwargs):
        user_id = self.request.user.pk
        platform = PlatformHelper.from_request(self.request)
        serializer = AudiomackOauthSerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        artist_id = serializer.validated_data["artist_id"]
        self.get_authorized_artist(artist_id, user_id)
        try:
            audiomack_oauth_api = AudiomackOauthAPI()
            token, token_secret = audiomack_oauth_api.get_request_token(platform)
            authorization_url = audiomack_oauth_api.get_authorize_url(token)
        except Exception:
            logger.exception("Audiomack oauth failed for user_id: %s " % user_id)
            return Response(
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
                data={'detail': 'Try again later'},
            )
        _set_cache(token, token_secret, user_id, artist_id)
        return Response(status=status.HTTP_200_OK, data={'url': authorization_url})

    def delete(self, request, *args, **kwargs):
        user_id = self.request.user.pk
        serializer = AudiomackOauthSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        artist_id = serializer.validated_data["artist_id"]
        artist = self.get_authorized_artist(artist_id, user_id)
        artist.audiomack_access_token = None
        artist.audiomack_access_token_secret = None
        artist.save()
        return Response(status=status.HTTP_204_NO_CONTENT)


class AudiomackCallbackView(ArtistAuthorizationMixin, logmixins.LogMixin, APIView):
    permission_classes = []

    def get(self, request, *args, **kwargs):
        serializer = AudiomackCallbackSerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        platform = data['platform']

        audiomack_key = 'audiomack/{}'.format(data["oauth_token"])
        audiomack_value = cache.get(audiomack_key)
        if not audiomack_value:
            # Oauth token not found in cache, either token not valid or has expired
            return CustomAmuseHttpResponseRedirect(
                _get_redirect_url(platform, success=False)
            )
        try:
            audiomack_oauth_api = AudiomackOauthAPI()
            audiomack_data = audiomack_oauth_api.get_access_token_and_artist_id(
                request_token=data['oauth_token'],
                request_token_secret=audiomack_value['request_token_secret'],
                oauth_verifier=data['oauth_verifier'],
            )
            if not audiomack_data:
                return CustomAmuseHttpResponseRedirect(
                    _get_redirect_url(platform, success=False)
                )
        except Exception:
            logger.exception("Failed to process")
            return CustomAmuseHttpResponseRedirect(
                _get_redirect_url(platform, success=False)
            )

        artist = self.get_authorized_artist(
            int(audiomack_value['artist_id']), int(audiomack_value['user_id'])
        )
        artist.audiomack_access_token = audiomack_data['oauth_token']
        artist.audiomack_access_token_secret = audiomack_data['oauth_token_secret']
        artist.audiomack_id = audiomack_data['artist_id']
        artist.save()

        return CustomAmuseHttpResponseRedirect(
            _get_redirect_url(platform, success=True)
        )
