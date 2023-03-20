import responses
from django.test import TestCase, override_settings
from django.core.management import call_command
from datetime import datetime, timedelta
from users.models import TeamInvitation
from users.tests.factories import TeamInvitationFactory

from amuse.tests.helpers import (
    add_zendesk_mock_post_response,
    ZENDESK_MOCK_API_URL_TOKEN,
)


@override_settings(**ZENDESK_MOCK_API_URL_TOKEN)
class UpdateExpiredTeamInvitation(TestCase):
    @responses.activate
    def setUp(self):
        add_zendesk_mock_post_response()

        today = datetime.now()
        yesterday = datetime.now() - timedelta(days=1)
        expired = datetime.now() - timedelta(days=40)

        self.create_team_invite(TeamInvitation.STATUS_PENDING, yesterday)
        self.create_team_invite(TeamInvitation.STATUS_PENDING, expired)
        self.create_team_invite(TeamInvitation.STATUS_PENDING, expired)
        self.create_team_invite(TeamInvitation.STATUS_ACCEPTED, today)
        self.create_team_invite(TeamInvitation.STATUS_DECLINED, today)
        self.create_team_invite(TeamInvitation.STATUS_EXPIRED, today)

    def create_team_invite(self, status, last_sent):
        ti = TeamInvitationFactory(status=status)
        ti.last_sent = last_sent
        ti.save()
        return ti

    def test_team_invitation_update_expired(self):
        call_command("update_expired_team_invitations")

        self.assertEqual(
            3,
            TeamInvitation.objects.filter(status=TeamInvitation.STATUS_EXPIRED).count(),
        )
        self.assertEqual(
            1,
            TeamInvitation.objects.filter(status=TeamInvitation.STATUS_PENDING).count(),
        )
        self.assertEqual(
            1,
            TeamInvitation.objects.filter(
                status=TeamInvitation.STATUS_ACCEPTED
            ).count(),
        )
        self.assertEqual(
            1,
            TeamInvitation.objects.filter(
                status=TeamInvitation.STATUS_DECLINED
            ).count(),
        )
