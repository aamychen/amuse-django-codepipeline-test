from rest_framework import serializers
from amuse.serializers import StringMapField
from users.models import UserArtistRole, ArtistV2, User


class RoleArtistSerializer(serializers.ModelSerializer):
    class Meta:
        model = ArtistV2
        fields = ('id', 'name')


class RoleUserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ('id', 'first_name', 'last_name', 'email')


class UserArtistRoleSerializer(serializers.ModelSerializer):
    type = StringMapField(mapping=UserArtistRole.TYPE_CHOICES)
    user = RoleUserSerializer(read_only=True)
    artist = RoleArtistSerializer(read_only=True)

    class Meta:
        model = UserArtistRole
        fields = ('id', 'type', 'user', 'artist')
        read_only_field = ('id', 'user', 'artist')
