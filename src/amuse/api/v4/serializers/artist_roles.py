from rest_framework import serializers
from rest_framework.fields import ListField

from releases.models.song import SongArtistRole
from users.models import ArtistV2


INVALID_ROLE_MESSAGE = "Invalid value for role"
CONFLICTING_ROLES_MESSAGE = (
    "An artist cannot be both a primary artist and featured artist"
)


class ArtistRolesSerializer(serializers.Serializer):
    artist_id = serializers.IntegerField()
    roles = ListField(allow_empty=False)
    artist_name = serializers.SerializerMethodField(read_only=True)

    def validate_roles(self, value):
        role_name_list = {role[1] for role in SongArtistRole.ROLE_CHOICES}
        for role_name in value:
            if role_name not in role_name_list:
                raise serializers.ValidationError(INVALID_ROLE_MESSAGE)

        if "primary_artist" in value and "featured_artist" in value:
            raise serializers.ValidationError(CONFLICTING_ROLES_MESSAGE)

        return value

    def get_artist_name(self, obj):
        try:
            return ArtistV2.objects.get(id=obj['artist_id']).name
        except:
            return ''
