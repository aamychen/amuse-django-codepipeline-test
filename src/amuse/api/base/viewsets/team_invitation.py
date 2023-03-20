import logging

from django.core.exceptions import ObjectDoesNotExist
from django.db import transaction
from amuse import mixins as logmixins
from rest_framework import mixins, permissions, viewsets, response, status
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError, NotFound
from rest_framework.response import Response
from django_filters import rest_framework as filters

from amuse.api.v4.serializers import TeamInvitationSerializer
from users.models import TeamInvitation, UserArtistRole
from amuse.permissions import CanManageTeamInvitationsPermission, FrozenUserPermission

logger = logging.getLogger(__name__)


class TeamInvitationViewSet(
    logmixins.LogMixin,
    mixins.ListModelMixin,
    mixins.CreateModelMixin,
    mixins.UpdateModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    permission_classes = (
        permissions.IsAuthenticated,
        CanManageTeamInvitationsPermission,
    )
    serializer_class = TeamInvitationSerializer
    filter_backends = (filters.DjangoFilterBackend,)
    filterset_fields = ('artist_id',)
    permission_denied_message = 'USER_NOT_PRO_OR_WITHOUT_AN_ARTIST'

    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update']:
            self.permission_classes = self.permission_classes + (FrozenUserPermission,)
        return [permission() for permission in self.permission_classes]

    def get_queryset(self):
        roles = UserArtistRole.objects.filter(user=self.request.user)
        artists = [role.artist for role in roles]

        return TeamInvitation.objects.filter(artist__in=artists)

    @action(
        detail=False, methods=['post'], permission_classes=[permissions.IsAuthenticated]
    )
    @transaction.atomic
    def confirm(self, request):
        token = request.data.get('token')
        if token is None:
            raise ValidationError({'token': 'missing team invitation token'})

        invitee = request.user
        try:
            invitation = TeamInvitation.objects.get(token=token)
        except ObjectDoesNotExist:
            logger.warning(f"Unable to find team invitation token={token}.")
            raise NotFound()
        else:
            if not invitation.valid:
                return Response(status=status.HTTP_404_NOT_FOUND)

            if invitee.userartistrole_set.filter(artist=invitation.artist).exists():
                raise ValidationError('User is already member of this artist team')

            # check if user is pro / has a team already
            if not invitee.is_pro and invitee.userartistrole_set.exists():
                return Response(
                    {'detail': self.permission_denied_message},
                    status=status.HTTP_403_FORBIDDEN,
                )

            invitation.status = TeamInvitation.STATUS_ACCEPTED
            invitation.save()

            UserArtistRole.objects.create(
                user=invitee, artist=invitation.artist, type=invitation.team_role
            )

            return Response(status=status.HTTP_202_ACCEPTED)

    def destroy(self, request, *args, **kwargs):
        invitation = self.get_object()
        invitation.status = TeamInvitation.STATUS_DECLINED
        invitation.save()
        return response.Response(status=status.HTTP_200_OK)
