import logging

from rest_framework.exceptions import ValidationError
from rest_framework.request import Request

from amuse.api.base.validators import validate_artist_name
from users.models import UserArtistRole, SongArtistInvitation, User
from .abstract_flow import AbstractFlow
from .common import Common

logger = logging.getLogger(__name__)


class SongInvitationFlow(AbstractFlow):
    def __init__(self, song_artist_invite_token: str):
        self.token = song_artist_invite_token
        self.invite = None

        super(SongInvitationFlow, self).__init__(False)

    def pre_registration(self, validated_data: dict) -> None:
        validate_artist_name(validated_data)

        self.invite = SongArtistInvitation.objects.filter(token=self.token).first()

        if self.invite is None:
            logger.warning(f'Song invite token="{self.token}" does not exist')
            raise ValidationError({"song_artist_invite_token": "Invalid token"})

        if not self.invite.valid:
            logger.warning(f'Song invite token="{self.token}" is not valid')
            raise ValidationError({"song_artist_invite_token": "Invalid token"})

    def post_registration(
        self, request: Request, user: User, validated_data: dict
    ) -> None:
        user.userartistrole_set.create(
            artist=self.invite.artist, type=UserArtistRole.OWNER
        )

        self.invite.status = SongArtistInvitation.STATUS_ACCEPTED
        self.invite.invitee = user
        self.invite.save()

        Common.send_signup_completed_event(request, user, "invite")
