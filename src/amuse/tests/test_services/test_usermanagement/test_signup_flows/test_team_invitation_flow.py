from unittest.mock import patch

from django.test import TestCase
from rest_framework.exceptions import ValidationError
from rest_framework.test import APIRequestFactory

from amuse.services.usermanagement.signup_flows import TeamInvitationFlow, Common
from users.models import TeamInvitation, UserArtistRole
from users.tests.factories import UserFactory, TeamInvitationFactory


class TestTeamInvitationFlowCase(TestCase):
    def test_pre_registration_fail_if_invite_does_not_exist(self):
        with self.assertRaises(ValidationError):
            TeamInvitationFlow('123').pre_registration({})

    @patch('amuse.tasks.zendesk_create_or_update_user')
    def test_pre_registration_fail_if_invite_status_is_not_pending(self, _):
        token = '123'
        inviter = UserFactory(artist_name=None)
        TeamInvitationFactory(
            inviter=inviter,
            invitee=None,
            token=token,
            status=TeamInvitation.STATUS_EXPIRED,
        )

        with self.assertRaises(ValidationError):
            TeamInvitationFlow(token).pre_registration({})

    @patch('amuse.tasks.zendesk_create_or_update_user')
    def test_pre_registration_fail_if_invitee_is_not_none(self, _):
        token = '123'
        inviter = UserFactory(artist_name=None)
        invitee = UserFactory(artist_name=None)
        TeamInvitationFactory(
            inviter=inviter,
            invitee=invitee,
            token=token,
            status=TeamInvitation.STATUS_PENDING,
        )

        with self.assertRaises(ValidationError):
            TeamInvitationFlow(token).pre_registration({})

    @patch(
        'amuse.services.usermanagement.signup_flows.royalty_invitation_flow.split_accepted'
    )
    @patch.object(Common, 'send_signup_completed_event')
    @patch('amuse.tasks.zendesk_create_or_update_user')
    def test_post_registration(
        self, _, mock_send_signup_completed_event, mock_split_accepted
    ):
        token = '123'
        user = UserFactory()
        inviter = UserFactory()
        invite = TeamInvitationFactory(
            inviter=inviter,
            invitee=None,
            token=token,
            status=TeamInvitation.STATUS_PENDING,
            team_role=TeamInvitation.TEAM_ROLE_MEMBER,
        )

        request = APIRequestFactory().post('/users')

        flow = TeamInvitationFlow(token)
        flow.invite = invite
        flow.post_registration(request, user, {})

        invite.refresh_from_db()
        self.assertEqual(invite.status, TeamInvitation.STATUS_ACCEPTED)

        exists = UserArtistRole.objects.filter(
            user_id=user.id, artist_id=invite.artist.id, type=UserArtistRole.MEMBER
        ).exists()

        self.assertTrue(exists)

        mock_send_signup_completed_event.assert_called_once_with(
            request, user, 'invite'
        )
