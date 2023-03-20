from rest_framework import serializers

from amuse.api.v4.serializers.helpers import filter_invite_sensitive_data
from amuse.serializers import StringMapField
from functools import cmp_to_key
from users.models import ArtistV2, UserArtistRole, User, TeamInvitation


class ArtistTeamRoleUserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ('id', 'first_name', 'last_name', 'email', 'profile_photo')


class ArtistTeamRoleSerializer(serializers.ModelSerializer):
    type = StringMapField(mapping=UserArtistRole.TYPE_CHOICES)
    user = ArtistTeamRoleUserSerializer()

    class Meta:
        model = UserArtistRole
        fields = ('id', 'type', 'user', 'created')


class ArtistTeamInviteSerializer(serializers.ModelSerializer):
    team_role = StringMapField(mapping=TeamInvitation.TEAM_ROLE_CHOICES)
    status = StringMapField(mapping=TeamInvitation.STATUS_CHOICES)

    class Meta:
        model = TeamInvitation
        fields = (
            'id',
            'email',
            'phone_number',
            'first_name',
            'last_name',
            'team_role',
            'status',
            'inviter',
            'last_sent',
        )


class ArtistTeamSerializer(serializers.ModelSerializer):
    roles = ArtistTeamRoleSerializer(source='userartistrole_set', many=True)
    invites = ArtistTeamInviteSerializer(source='teaminvitation_set', many=True)

    class Meta:
        model = ArtistV2
        fields = ('roles', 'invites')

    def to_representation(self, data):
        to_return = super().to_representation(data)
        invites = to_return.get('invites')

        valid = (
            TeamInvitation.get_status_name(TeamInvitation.STATUS_PENDING),
            TeamInvitation.get_status_name(TeamInvitation.STATUS_EXPIRED),
        )

        invites_filtered = [i for i in invites if i['status'] in valid]

        user = self.context['user']
        artist_id = self.context['artist_id']
        artist = ArtistV2.objects.get(id=artist_id)

        if not user.is_admin_of_artist_team(artist):
            invites_filtered = filter_invite_sensitive_data(invites_filtered)

        to_return['invites'] = invites_filtered
        to_return['roles'] = sort_artist_team_roles(user.pk, to_return['roles'])

        return to_return


def sort_artist_team_roles(user_id, roles):
    """
    User's account is on top,
    then show Owner,
    then chronologically when added (NOT accepted by recipient and NOT by permissions level).
    """
    users_roles = []
    rest_roles = []

    for role in roles:
        users_roles.append(role) if role['user'][
            'id'
        ] == user_id else rest_roles.append(role)

    users_roles.sort(key=cmp_to_key(artist_team_role_comparator))
    rest_roles.sort(key=cmp_to_key(artist_team_role_comparator))

    return users_roles + rest_roles


def artist_team_role_comparator(item1, item2):
    owner_role = UserArtistRole.get_name(UserArtistRole.OWNER)

    if item1['type'] == owner_role:
        return -1

    if item2['type'] == owner_role:
        return 1

    if item1['created'] > item2['created']:
        return 1

    if item1['created'] < item2['created']:
        return -1

    return 0
