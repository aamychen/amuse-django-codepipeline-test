from django.test import TestCase
from rest_framework.exceptions import ValidationError
from rest_framework.test import APIRequestFactory
from amuse.services.usermanagement.signup_flows import SongInvitationFlow, Common
from users.models import SongArtistInvitation
from releases.tests.factories import SongFactory
from users.tests.factories import (
    UserFactory,
    Artistv2Factory,
    SongArtistInvitationFactory,
)
from unittest.mock import patch


class TestSongArtistInvitationFlowCase(TestCase):
    def test_pre_registration_fail_if_artist_name_is_empy(self):
        with self.assertRaises(ValidationError):
            SongInvitationFlow('123').pre_registration({'artist_name': ''})

    def test_pre_registration_fail_if_invite_does_not_exist(self):
        with self.assertRaises(ValidationError):
            SongInvitationFlow('123').pre_registration({})

    @patch('amuse.tasks.zendesk_create_or_update_user')
    def test_pre_registration_fail_if_invite_is_not_valid(self, _):
        token = '123'
        song = SongFactory()
        inviter = UserFactory()
        artist = Artistv2Factory(name='I am invited')
        SongArtistInvitationFactory(
            inviter=inviter,
            artist=artist,
            song=song,
            token=token,
            status=SongArtistInvitation.STATUS_CREATED,
        )

        with self.assertRaises(ValidationError):
            SongInvitationFlow('123').pre_registration({})

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
        song = SongFactory()
        inviter = UserFactory()
        artist = Artistv2Factory(name='I am invited')
        invite = SongArtistInvitationFactory(
            inviter=inviter,
            artist=artist,
            song=song,
            token=token,
            status=SongArtistInvitation.STATUS_PENDING,
        )
        request = APIRequestFactory().post('/users')

        flow = SongInvitationFlow(token)
        flow.invite = invite
        flow.post_registration(request, user, {})

        invite.refresh_from_db()
        self.assertEqual(invite.status, SongArtistInvitation.STATUS_ACCEPTED)
        self.assertEqual(invite.invitee.id, user.id)

        mock_send_signup_completed_event.assert_called_once_with(
            request, user, 'invite'
        )
