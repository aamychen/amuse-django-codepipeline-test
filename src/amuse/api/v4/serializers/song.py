from decimal import Decimal

from django.utils import timezone
from rest_framework import serializers
from rest_framework.fields import SerializerMethodField, ListField, Field

from amuse.api.base.validators import (
    validate_genre,
    validate_audio_s3_key,
    validate_audio_url,
    validate_language,
)
from amuse.api.base.views.exceptions import ProPermissionError
from amuse.api.v4.serializers.artist_roles import ArtistRolesSerializer
from amuse.api.v4.serializers.genre import GenreSerializer
from amuse.api.v4.serializers.helpers import (
    is_valid_split_for_free_user,
    get_serialized_active_royalty_splits,
)
from amuse.api.v4.serializers.royalty_split import RoyaltySplitSerializer
from amuse.serializers import BitFieldField, PlaceholderCharField, StringMapField
from releases.models import Song, RoyaltySplit
from users.models import ArtistV2


class SongSerializer(serializers.Serializer):
    id = serializers.IntegerField(read_only=True)
    name = serializers.CharField()
    filename = PlaceholderCharField(max_length=255, allow_blank=True, placeholder='N/A')
    sequence = serializers.IntegerField()
    recording_year = serializers.IntegerField(
        min_value=1000, max_value=timezone.now().year
    )
    original_release_date = serializers.DateField(required=False, allow_null=True)
    origin = StringMapField(mapping=Song.ORIGIN_CHOICES)
    explicit = StringMapField(mapping=Song.EXPLICIT_CHOICES)
    version = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    isrc = serializers.RegexField(
        regex='[A-Z]{2}[A-Z0-9]{3}[0-9]{7}',
        min_length=12,
        max_length=12,
        required=False,
        allow_null=True,
        allow_blank=True,
    )

    genre = GenreSerializer(validators=[validate_genre])
    artists_roles = ArtistRolesSerializer(many=True)
    artists_invites = ListField(required=False, allow_null=True)
    royalty_splits = RoyaltySplitSerializer(many=True)

    error_flags = BitFieldField(flags=Song.error_flags.items(), read_only=True)
    youtube_content_id = StringMapField(mapping=Song.YT_CONTENT_ID_CHOICES)
    cover_licensor = serializers.CharField(required=False, allow_blank=True)

    audio_s3_key = serializers.CharField(
        validators=[validate_audio_s3_key],
        required=False,
        allow_null=True,
        allow_blank=True,
        write_only=True,
    )
    audio_dropbox_link = serializers.CharField(
        validators=[validate_audio_url],
        required=False,
        allow_null=True,
        allow_blank=True,
        write_only=True,
    )
    audio_gdrive_auth_code = serializers.CharField(
        required=False, allow_null=True, allow_blank=True, write_only=True
    )
    audio_gdrive_file_id = serializers.CharField(
        required=False, allow_null=True, allow_blank=True, write_only=True
    )

    language_code = serializers.CharField(
        write_only=True, required=False, allow_null=True, validators=[validate_language]
    )

    audio_language_code = serializers.CharField(
        write_only=True, required=False, allow_null=True, validators=[validate_language]
    )

    preview_start_time = serializers.IntegerField(
        required=False,
        allow_null=True,
        min_value=0,
    )

    def validate_royalty_splits(self, value):
        user_list = [split["user_id"] for split in value if split.get("user_id")]
        unique_user_list = list(set(user_list))

        if sorted(user_list) != sorted(unique_user_list):
            raise serializers.ValidationError(
                "Duplicate user_id defined. user_id must be unique. "
            )

        total_rates = sum([royalty_split['rate'] for royalty_split in value])

        if total_rates != Decimal(1):
            raise serializers.ValidationError(
                "The sum of the royalty splits' rates is not equal to 1"
            )

        return value

    def validate_artists_roles(self, value):
        """Validates that artists roles are not an empty"""
        if value:
            return value
        else:
            raise serializers.ValidationError("Artists' roles are required.")

    def validate_preview_start_time(self, value):
        if not value:
            return value
        user = self.context['request'].user
        if user.tier == user.TIER_FREE:
            raise ProPermissionError()
        return value

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data["royalty_splits"] = get_serialized_active_royalty_splits(instance)
        return data
