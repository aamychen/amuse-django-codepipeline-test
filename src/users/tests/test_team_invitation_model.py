from django.test import TestCase
from django.utils import timezone

from .factories import TeamInvitationFactory
from ..models import TeamInvitation


class TeamInvitationModelTestCase(TestCase):
    def test_get_status_name(self):
        self.assertEqual(
            'pending', TeamInvitation.get_status_name(TeamInvitation.STATUS_PENDING)
        )
        self.assertEqual(
            'expired', TeamInvitation.get_status_name(TeamInvitation.STATUS_EXPIRED)
        )
        self.assertEqual(
            'accepted', TeamInvitation.get_status_name(TeamInvitation.STATUS_ACCEPTED)
        )
        self.assertEqual(
            'declined', TeamInvitation.get_status_name(TeamInvitation.STATUS_DECLINED)
        )

    def test_expiration_date(self):
        date = timezone.now() + timezone.timedelta(days=-29)
        expired_date = timezone.now() + timezone.timedelta(days=-31)

        invitation = TeamInvitationFactory()

        invitation.last_sent = date
        invitation.save()
        self.assertTrue(invitation.valid)

        invitation.last_sent = expired_date
        invitation.save()
        self.assertTrue(invitation.valid)

        invitation.last_sent = expired_date
        invitation.status = TeamInvitation.STATUS_EXPIRED
        invitation.save()
        self.assertFalse(invitation.valid)

    def test_accepted_invitation_is_not_valid_anymore(self):
        invitation = TeamInvitationFactory()

        invitation.status = TeamInvitation.STATUS_ACCEPTED
        invitation.save()
        invitation.refresh_from_db()

        self.assertFalse(invitation.valid)
