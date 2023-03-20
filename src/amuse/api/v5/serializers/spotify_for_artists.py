import logging

from django.core.signing import BadSignature
from rest_framework import serializers
from rest_framework.exceptions import ValidationError

from amuse.analytics import s4a_connected
from amuse.api.helpers import get_artist
from amuse.vendor.spotify.artists import (
    SpotifyException,
    build_authorize_url,
    create_access_token,
    create_invite_url,
    get_artist_spotify_id_and_release_uri,
    parse_state,
)
from releases.models import Release, ReleaseArtistRole, Store

logger = logging.getLogger(__name__)


class SpotifyForArtistsSerializer(serializers.Serializer):
    artist_id = serializers.IntegerField(required=True)

    def validate_artist_id(self, artist_id):
        return get_artist(artist_id, self.context['request'].user.pk)

    def validate(self, data):
        user = self.context['request'].user
        artist = data['artist_id']
        url = artist.spotify_for_artists_url

        if not url:
            get_spotify_uris(artist, user.pk)

        if not (artist.spotify_id and url and url.endswith(artist.spotify_id)):
            # Artist does not yet have S4A
            url = build_authorize_url(user.pk, artist.pk)
        self.url = url
        return data


class SpotifyForArtistsCallbackSerializer(serializers.Serializer):
    state = serializers.CharField(required=True)
    code = serializers.CharField(required=True)

    def validate_state(self, state):
        try:
            return parse_state(state)
        except BadSignature:
            raise ValidationError('Invalid state')

    def validate(self, data):
        user_id, artist_id = data['state']
        artist = get_artist(artist_id, user_id)
        artist_spotify_id, release_uri = get_spotify_uris(artist, user_id)

        artist_uri = f'spotify:artist:{artist_spotify_id}'

        try:
            access_token = create_access_token(user_id, artist_id, data['code'])
        except SpotifyException as e:
            logger.info(
                f'S4A: Failed creating access token for user {user_id} and artist {artist.id}. {e.message}'
            )
            raise ValidationError(e.status_code)

        try:
            url = create_invite_url(access_token, artist_uri, release_uri)
        except SpotifyException as e:
            logger.info(
                f'S4A: Failed creating invite url for user {user_id} and artist {artist.id}. {e.message}'
            )
            raise ValidationError(e.status_code)

        artist.spotify_id = artist_spotify_id
        artist.spotify_for_artists_url = url
        artist.save()

        s4a_connected(user_id, artist_id)

        self.url = url
        return data


class SpotifyForArtistsDisconnectSerializer(serializers.Serializer):
    artist_id = serializers.IntegerField(required=True)


def get_spotify_uris(artist, user_id):
    spotify_store_id = Store.objects.get(name='Spotify', active=True).pk
    release_ids = ReleaseArtistRole.objects.filter(artist=artist).values_list(
        'release_id', flat=True
    )
    releases = Release.objects.filter(
        pk__in=release_ids, status=Release.STATUS_RELEASED
    )
    for release in releases:
        if release.stores.filter(pk=spotify_store_id).exists():
            try:
                artist_spotify_id, release_uri = get_artist_spotify_id_and_release_uri(
                    release.upc
                )
                if artist_spotify_id is not None and release_uri is not None:
                    return artist_spotify_id, release_uri
            except SpotifyException as e:
                logger.info(
                    f'S4A: Failed getting spotify uri for user {user_id} and artist {artist.id}. {e.message}'
                )
                raise ValidationError(e.status_code)

    raise ValidationError({'artist_id': ['Artist has no release on Spotify']})
