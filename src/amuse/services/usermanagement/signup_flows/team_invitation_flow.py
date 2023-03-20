import logging

from rest_framework.exceptions import ValidationError
from rest_framework.request import Request

from users.models import User, TeamInvitation, UserArtistRole
from .abstract_flow import AbstractFlow
from .common import Common

logger = logging.getLogger(__name__)


class TeamInvitationFlow(AbstractFlow):
    def __init__(self, user_artist_role_token: str):
        self.token = user_artist_role_token
        self.invite = None

        super(TeamInvitationFlow, self).__init__(True)

    def pre_registration(self, validated_data: dict) -> None:
        token = self.token
        self.invite = TeamInvitation.objects.filter(token=token).first()

        if self.invite is None:
            logger.warning(f'Team invite token="{token}" does not exist')
            raise ValidationError({"user_artist_role_token": "Invalid token"})

        if not self.invite.valid or self.invite.invitee is not None:
            logger.warning(f'Song invite token="{token}" is not valid')
            raise ValidationError({"song_artist_invite_token": "Invalid token"})

    def post_registration(
        self, request: Request, user: User, validated_data: dict
    ) -> None:
        self.invite.status = TeamInvitation.STATUS_ACCEPTED
        self.invite.save()

        user_artist_role = UserArtistRole(
            user=user, artist=self.invite.artist, type=self.invite.team_role
        )
        user_artist_role.save()

        Common.send_signup_completed_event(request, user, "invite")
