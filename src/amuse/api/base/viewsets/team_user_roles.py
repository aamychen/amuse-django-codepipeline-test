from rest_framework import mixins, permissions, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters import rest_framework as filters

from amuse import mixins as logmixins
from amuse.api.v4.serializers import UserArtistRoleSerializer
from users.models import UserArtistRole
from amuse.permissions import (
    CanManageTeamRolesPermission,
    CanUpdateToTeamRolePermission,
)
from amuse.tasks import (
    send_team_member_role_updated_emails,
    send_team_member_role_removed_emails,
)


class TeamUserRolesViewSet(
    logmixins.LogMixin,
    mixins.ListModelMixin,
    mixins.UpdateModelMixin,
    mixins.DestroyModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    permission_classes = (
        permissions.IsAuthenticated,
        CanManageTeamRolesPermission,
        CanUpdateToTeamRolePermission,
    )
    serializer_class = UserArtistRoleSerializer
    queryset = UserArtistRole.objects.all()
    filter_backends = (filters.DjangoFilterBackend,)
    filterset_fields = ('artist_id',)

    def get_queryset(self):
        user_artist_ids = UserArtistRole.objects.filter(
            user=self.request.user
        ).values_list('artist_id', flat=True)
        return UserArtistRole.objects.filter(artist_id__in=user_artist_ids)

    def perform_update(self, serializer):
        super().perform_update(serializer)

        artist = serializer.instance.artist
        member_user = serializer.instance.user
        admin_user = self.request.user
        owner_user = artist.owner
        new_role = serializer.instance.type

        # Send notification emails for team member role update
        send_team_member_role_updated_emails.delay(
            {
                "user_id": self.request.user.id,
                "artist_name": artist.name,
                "member_email": member_user.email,
                "member_first_name": member_user.first_name,
                "member_last_name": member_user.last_name,
                "admin_first_name": admin_user.first_name,
                "admin_last_name": admin_user.last_name,
                "owner_email": owner_user.email,
                "owner_first_name": owner_user.first_name,
                "owner_last_name": owner_user.last_name,
                "role": new_role,
                "is_self_update": admin_user == member_user,
                "is_updated_by_owner": admin_user == owner_user,
            }
        )

    def perform_destroy(self, instance):
        artist = instance.artist
        member_user = instance.user
        admin_user = self.request.user
        owner_user = artist.owner

        super().perform_destroy(instance)

        # Send notification emails for team member removal
        send_team_member_role_removed_emails.delay(
            {
                "user_id": self.request.user.id,
                "artist_name": artist.name,
                "member_email": member_user.email,
                "member_first_name": member_user.first_name,
                "member_last_name": member_user.last_name,
                "admin_first_name": admin_user.first_name,
                "admin_last_name": admin_user.last_name,
                "owner_email": owner_user.email,
                "owner_first_name": owner_user.first_name,
                "owner_last_name": owner_user.last_name,
                "is_self_removal": admin_user == member_user,
                "is_removed_by_owner": admin_user == owner_user,
                "role": instance.type,
            }
        )

    @action(detail=False)
    def own(self, request):
        user = self.request.user
        queryset = self.filter_queryset(self.get_queryset()).filter(user=user)

        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)
