import logging
from django.core.exceptions import EmptyResultSet
from django.http import Http404
from rest_framework import generics, status
from rest_framework.decorators import permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from amuse.api.v4.serializers.artist import ArtistSearchSerializer
from amuse.api.v4.serializers.blacklisted_artist_name import (
    BlacklistedArtistNameSerializer,
)
from amuse.api.base.views.exceptions import (
    BadQueryParameterException,
    WrongAPIversionError,
    MissingQueryParameterError,
)
from amuse.vendor.spotify.artist_blacklist.blacklist import fuzzify
from releases.models.exceptions import (
    SongsIDsDoNotExistError,
    ArtistsIDsDoNotExistError,
)
from releases.models.blacklisted_artist_name import BlacklistedArtistName
from releases.models.release import ReleaseArtistRole, Release
from releases.models.song import Song, SongArtistRole
from users.models.artist_v2 import UserArtistRole, ArtistV2
from users.models.exceptions import ArtistsDoNotExistError


logger = logging.getLogger(__name__)


@permission_classes([IsAuthenticated])
class ArtistSearchView(generics.ListAPIView):
    """
    This does only have basic authentication restrictions and any additional permission
    logic should be implemented in the calling side.
    """

    serializer_class = ArtistSearchSerializer

    def get_queryset(self):
        if self.request.version == '4':
            spotify_id = self.request.query_params.get('spotify_id', None)

            if spotify_id is not None:
                artists = ArtistV2.objects.filter(spotify_id=spotify_id)

                if artists.exists():
                    return artists
                else:
                    raise EmptyResultSet()
            else:
                raise BadQueryParameterException()
        else:
            raise WrongAPIversionError()

    def list(self, request, *args, **kwargs):
        try:
            response = super().list(request, *args, **kwargs)
        except BadQueryParameterException as e:
            response = Response(status=status.HTTP_400_BAD_REQUEST)
        except EmptyResultSet as e:
            response = Response(status=status.HTTP_404_NOT_FOUND)

        return response


@permission_classes([IsAuthenticated])
class RelatedArtistView(generics.ListAPIView):
    serializer_class = ArtistSearchSerializer

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        if not self.request.version == '4':
            raise WrongAPIversionError()
        if 'artist_id' not in self.request.query_params:
            raise MissingQueryParameterError()

    def get_queryset(self):
        artist_id = self.request.query_params.get('artist_id')
        try:
            songs_ids = SongArtistRole.get_songs_ids_by_artist_id(artist_id)
            artists_ids = SongArtistRole.get_artists_ids_by_songs_ids(
                artist_id, songs_ids
            )

            return ArtistV2.get_artists_by_ids(artists_ids)
        except (
            SongsIDsDoNotExistError,
            ArtistsIDsDoNotExistError,
            ArtistsDoNotExistError,
        ) as e:
            logger.debug(e.message)
            raise Http404()


@permission_classes([IsAuthenticated])
class BlacklistedArtistNameSearchView(generics.ListAPIView):
    serializer_class = BlacklistedArtistNameSerializer

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        if not self.request.version == '4':
            raise WrongAPIversionError()
        if 'name' not in self.request.query_params:
            raise MissingQueryParameterError(
                detail='Name is missing from query parameters.'
            )

    def get_queryset(self):
        name = self.request.query_params.get('name')
        fuzzy_name = fuzzify(name)
        return BlacklistedArtistName.objects.filter(fuzzy_name=fuzzy_name)
