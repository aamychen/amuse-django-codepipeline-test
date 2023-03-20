import logging

from django.utils import timezone

from amuse.vendor.customerio.events import default as cioevents
from users.models import RoyaltyInvitation


logger = logging.getLogger(__name__)


def send_royalty_invite(invite, split, token):
    release = split.song.release
    data = {
        'inviter_id': release.user.id,
        'invitee_id': invite.invitee_id,
        'invitee_name': invite.name,
        'inviter_first_name': release.user.first_name,
        'inviter_last_name': release.user.last_name,
        'token': token,
        'song_name': split.song.name,
        'release_date': release.release_date,
        'royalty_rate': f'{float(split.rate):.2%}',
        'expiration_time': invite.expiration_time.strftime("%m/%d/%Y, %H:%M"),
    }

    if invite.invitee_id is None:
        cioevents().send_royalty_invite(invite.email, invite.phone_number, data)
    else:
        cioevents().send_royalty_assigned_to_existing_user(
            split.user_id, invite.phone_number, data
        )

    invite.last_sent = timezone.now()
    invite.token = token
    invite.status = RoyaltyInvitation.STATUS_PENDING
    invite.save()

    logger.info(
        "Sent royalty invitation for invite_id %s, release_id %s inviter_id %s, invitee_id %s and split_id %s"
        % (invite.id, invite.inviter_id, invite.invitee_id, release.id, split.id)
    )
