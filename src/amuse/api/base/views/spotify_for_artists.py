from django.http import HttpResponseRedirect
from rest_framework import status
from rest_framework.generics import ListAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from amuse import mixins as logmixins
from amuse.api.base.mixins import ArtistAuthorizationMixin
from amuse.api.base.views.exceptions import WrongAPIversionError
from amuse.api.v5.serializers.spotify_for_artists import (
    SpotifyForArtistsCallbackSerializer,
    SpotifyForArtistsSerializer,
    SpotifyForArtistsDisconnectSerializer,
)


class SpotifyForArtistsView(logmixins.LogMixin, ListAPIView):
    permission_classes = [IsAuthenticated]

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        if self.request.version != '5':
            raise WrongAPIversionError()

    def get(self, request, *args, **kwargs):
        serializer = SpotifyForArtistsSerializer(
            data=request.GET, context={'request': request}
        )
        serializer.is_valid(raise_exception=True)
        return Response({'url': serializer.url})


class SpotifyForArtistsCallbackView(logmixins.LogMixin, ListAPIView):
    permission_classes = []

    def get(self, request, *args, **kwargs):
        serializer = SpotifyForArtistsCallbackSerializer(data=request.GET)
        serializer.is_valid(raise_exception=True)
        return HttpResponseRedirect(serializer.url)


class SpotifyForArtistsDisconnectView(
    ArtistAuthorizationMixin, logmixins.LogMixin, APIView
):
    permission_classes = [IsAuthenticated]

    def delete(self, request, *args, **kwargs):
        user_id = self.request.user.pk
        serializer = SpotifyForArtistsDisconnectSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        artist_id = serializer.validated_data["artist_id"]
        artist = self.get_authorized_artist(artist_id, user_id)
        artist.spotify_for_artists_url = None
        artist.save()
        return Response(status=status.HTTP_204_NO_CONTENT)
