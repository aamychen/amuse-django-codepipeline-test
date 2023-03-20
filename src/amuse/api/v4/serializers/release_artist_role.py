from rest_framework import serializers

from amuse.serializers import StringMapField
from releases.models import ReleaseArtistRole


class ReleaseArtistRoleSerializer(serializers.ModelSerializer):
    class Meta:
        model = ReleaseArtistRole
        fields = (
            'artist_id',
            'artist_name',
            'role',
        )
        read_only_fields = (
            'artist_id',
            'artist_name',
            'role',
        )

    artist_name = serializers.SerializerMethodField()
    role = StringMapField(mapping=ReleaseArtistRole.ROLE_CHOICES)

    def get_artist_name(self, obj):
        return obj.artist.name
