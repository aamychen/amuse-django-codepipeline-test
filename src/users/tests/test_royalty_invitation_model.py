from django.test import TestCase
from django.utils import timezone
from datetime import timedelta

from unittest.mock import patch
from ..models import RoyaltyInvitation


class RoyaltyInvitationModelTestCase(TestCase):
    def test_expiration_date(self):
        date = timezone.now() + timezone.timedelta(days=-29)
        expired_date = timezone.now() + timezone.timedelta(days=-31)

        invitation = RoyaltyInvitation(status=RoyaltyInvitation.STATUS_PENDING)
        invitation.last_sent = date

        self.assertTrue(invitation.valid)

        invitation = RoyaltyInvitation(status=RoyaltyInvitation.STATUS_CREATED)
        invitation.last_sent = date
        self.assertFalse(invitation.valid)

        invitation.status = RoyaltyInvitation(status=RoyaltyInvitation.STATUS_PENDING)
        invitation.last_sent = expired_date
        self.assertFalse(invitation.valid)

        invitation.status = RoyaltyInvitation(status=RoyaltyInvitation.STATUS_PENDING)
        invitation.last_sent = None
        self.assertFalse(invitation.valid)

    @patch('django.utils.timezone.now')
    def test_expiration_time(self, mock_time_now):
        mock_time_now.return_value = timezone.datetime(2010, 1, 1)

        invitation = RoyaltyInvitation(status=RoyaltyInvitation.STATUS_PENDING)

        invitation.last_sent = None
        expiration_time = timezone.now() + timedelta(days=invitation.EXPIRATION_DAYS)
        self.assertEqual(expiration_time, invitation.expiration_time)

        invitation.last_sent = timezone.datetime(2010, 1, 20)
        expiration_time = invitation.last_sent + timedelta(
            days=invitation.EXPIRATION_DAYS
        )
        self.assertEqual(expiration_time, invitation.expiration_time)

    def test_accepted_invitation_is_not_valid_anymore(self):
        invitation = RoyaltyInvitation()
        invitation.last_sent = timezone.now() + timezone.timedelta(days=-29)
        invitation.status = RoyaltyInvitation.STATUS_ACCEPTED

        self.assertFalse(invitation.valid)
