import logging

from rest_framework.exceptions import ValidationError
from rest_framework.request import Request

from amuse.analytics import split_accepted
from releases.models import RoyaltySplit
from users.models import RoyaltyInvitation, User
from .abstract_flow import AbstractFlow
from .common import Common
from amuse.api.v4.serializers.helpers import update_splits_state

logger = logging.getLogger(__name__)


class RoyaltyInvitationFlow(AbstractFlow):
    def __init__(self, royalty_token: str):
        self.royalty_token = royalty_token
        self.invite = None

        super(RoyaltyInvitationFlow, self).__init__(True)

    def pre_registration(self, validated_data: dict) -> None:
        token = self.royalty_token

        invite = RoyaltyInvitation.objects.filter(token=token).first()
        if invite is None:
            logger.warning(f'Royalty invite token="{token}" does not exist')
            raise ValidationError({"royalty_token": "Invalid token"})

        if not invite.valid:
            logger.warning(f'Royalty invite token="{token}" is not valid')
            raise ValidationError({"royalty_token": "Invalid token"})

        if invite.invitee is None:
            msg = f'Royalty invite token="{token}", invite is created for existing user'
            logger.warning(msg)
            raise ValidationError({"royalty_token": "Invalid token"})

    def post_registration(
        self, request: Request, user: User, validated_data: dict
    ) -> None:
        self.invite.status = RoyaltyInvitation.STATUS_ACCEPTED
        self.invite.invitee = user
        self.invite.save()

        self.invite.royalty_split.status = RoyaltySplit.STATUS_CONFIRMED
        self.invite.royalty_split.user = user
        self.invite.royalty_split.save()

        update_splits_state(
            self.invite.royalty_split.song, self.invite.royalty_split.revision
        )
        Common.send_signup_completed_event(request, user, "invite")
        split_accepted(self.invite.royalty_split)
