import re
from logging import getLogger

from rest_framework import serializers
from rest_framework.exceptions import ValidationError
from rest_framework.fields import SerializerMethodField

from amuse.api.actions.release import get_writers_from_history
from amuse.api.base.validators import validate_tiktok_name
from amuse.api.base.validators import validate_artist_spotify_id
from amuse.api.v4.serializers.helpers import fetch_spotify_image
from amuse.settings.constants import SPOTIFY_ARTIST_URL
from amuse.utils import match_strings
from amuse.vendor.audiomack.audiomack_api import AudiomackAPI
from releases.models import ReleaseArtistRole, Release
from users.models import ArtistV2, UserArtistRole, User

logger = getLogger(__name__)


class ArtistOwnerSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ('id', 'first_name', 'last_name', 'profile_photo')


class ArtistSerializer(serializers.ModelSerializer):
    role = SerializerMethodField()
    releases_count = SerializerMethodField()
    owner = ArtistOwnerSerializer(read_only=True)
    spotify_id = serializers.CharField(
        validators=[validate_artist_spotify_id],
        required=False,
        allow_null=True,
        allow_blank=True,
    )
    spotify_image = serializers.CharField(
        required=False, allow_null=True, allow_blank=True
    )
    main_artist_profile = SerializerMethodField(read_only=True)
    has_spotify_for_artists = SerializerMethodField(read_only=True)
    has_audiomack = SerializerMethodField(read_only=True)
    audiomack_profile_url = SerializerMethodField(read_only=True)
    spotify_profile_url = SerializerMethodField(read_only=True)

    class Meta:
        model = ArtistV2
        fields = (
            'id',
            'name',
            'created',
            'spotify_page',
            'twitter_name',
            'facebook_page',
            'instagram_name',
            'tiktok_name',
            'soundcloud_page',
            'youtube_channel',
            'spotify_id',
            'spotify_image',
            'apple_id',
            'has_owner',
            'role',
            'releases_count',
            'owner',
            'main_artist_profile',
            'has_spotify_for_artists',
            'has_audiomack',
            'audiomack_profile_url',
            'spotify_profile_url',
        )
        read_only_fields = (
            'id',
            'created',
            'has_owner',
            'owner',
            'spotify_image',
            'main_artist_profile',
        )

    def get_role(self, obj):
        return dict(UserArtistRole.TYPE_CHOICES)[
            self.context['request'].user.userartistrole_set.get(artist_id=obj.pk).type
        ]

    def get_releases_count(self, artist):
        return (
            ReleaseArtistRole.objects.filter(
                artist=artist, role=ReleaseArtistRole.ROLE_PRIMARY_ARTIST
            )
            .exclude(
                release__status__in=[Release.STATUS_DELETED, Release.STATUS_REJECTED]
            )
            .count()
        )

    def get_main_artist_profile(self, obj):
        return (
            self.context['request']
            .user.userartistrole_set.get(artist_id=obj.pk)
            .main_artist_profile
        )

    def get_audiomack_profile_url(self, artist):
        if artist.audiomack_access_token and artist.audiomack_access_token_secret:
            try:
                api = AudiomackAPI(
                    artist.audiomack_access_token, artist.audiomack_access_token_secret
                )
                url = api.get_artist_profile_url()
                api.close_session()
                return url
            except Exception as err:
                logger.warning(
                    f'Unable to get audiomack profile url for artist: {artist.id}, err: {err}'
                )
        return None

    def get_spotify_profile_url(self, artist):
        return (
            SPOTIFY_ARTIST_URL.format(artist.spotify_id) if artist.spotify_id else None
        )

    def get_has_spotify_for_artists(self, artist):
        url = artist.spotify_for_artists_url
        return bool(url and len(url) > 0)

    def get_has_audiomack(self, artist):
        return artist.audiomack_access_token is not None

    def create(self, validated_data):
        user = self.context['request'].user

        spotify_image = fetch_spotify_image(
            validated_data.get('spotify_id', None),
            validated_data.get('spotify_image', None),
        )
        validated_data['spotify_image'] = spotify_image

        return user.create_artist_v2(**validated_data)

    def update(self, instance, validated_data):
        # disable changing artist name
        if validated_data.get('name') != instance.name:
            raise ValidationError('Updating Artist name is not allowed')

        return super().update(instance, validated_data)


class ArtistSoMeUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = ArtistV2
        fields = (
            'spotify_page',
            'twitter_name',
            'facebook_page',
            'instagram_name',
            'tiktok_name',
            'soundcloud_page',
            'youtube_channel',
            'spotify_id',
        )

    def validate_tiktok_name(self, value):
        return validate_tiktok_name(value, error=serializers.ValidationError)


class ArtistSearchSerializer(serializers.ModelSerializer):
    class Meta:
        model = ArtistV2
        fields = (
            'id',
            'name',
            'created',
            'spotify_id',
            'apple_id',
            'has_owner',
            'spotify_image',
        )


class ContibutorArtistSerializer(serializers.ModelSerializer):
    class Meta:
        model = ArtistV2
        fields = ('id', 'name', 'spotify_id', 'has_owner')
        read_only_fields = ('id', 'has_owner')

    def create(self, validated_data):
        user = self.context['request'].user
        name = validated_data.get('name')
        spotify_id = validated_data.get('spotify_id')
        writers = get_writers_from_history(user)
        for writer in writers:
            if spotify_id and spotify_id == writer.spotify_id:
                return writer
            if match_strings(name, writer.name):
                return writer
        artist = ArtistV2.objects.create(name=name, spotify_id=spotify_id)
        return artist
