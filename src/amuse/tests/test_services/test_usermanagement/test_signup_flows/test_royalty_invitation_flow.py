from decimal import Decimal
from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone
from rest_framework.exceptions import ValidationError
from rest_framework.test import APIRequestFactory


from amuse.services.usermanagement.signup_flows import RoyaltyInvitationFlow, Common
from releases.models import RoyaltySplit
from releases.tests.factories import SongFactory, RoyaltySplitFactory
from users.models import RoyaltyInvitation
from users.tests.factories import UserFactory, RoyaltyInvitationFactory


class TestRoyaltyInvitationFlowCase(TestCase):
    def test_pre_registration_fail_if_invite_does_not_exist(self):
        with self.assertRaises(ValidationError):
            RoyaltyInvitationFlow('123').pre_registration({})

    @patch('amuse.tasks.zendesk_create_or_update_user')
    def test_pre_registration_fail_if_invite_is_not_valid(self, _):
        inviter = UserFactory(artist_name=None)
        song = SongFactory()
        split = RoyaltySplitFactory(song=song, user=inviter, rate=Decimal('1'))

        token = '123'
        RoyaltyInvitationFactory(
            inviter=inviter,
            token=token,
            status=RoyaltyInvitation.STATUS_DECLINED,
            royalty_split=split,
            last_sent=timezone.now(),
        )
        with self.assertRaises(ValidationError):
            RoyaltyInvitationFlow(token).pre_registration({})

    @patch('amuse.tasks.zendesk_create_or_update_user')
    def test_pre_registration_fail_if_invitee_is_none(self, _):
        inviter = UserFactory(artist_name=None)
        song = SongFactory()
        split = RoyaltySplitFactory(song=song, user=inviter, rate=Decimal('1'))

        token = '123'
        RoyaltyInvitationFactory(
            inviter=inviter,
            token=token,
            status=RoyaltyInvitation.STATUS_PENDING,
            royalty_split=split,
            last_sent=timezone.now(),
        )
        with self.assertRaises(ValidationError):
            RoyaltyInvitationFlow(token).pre_registration({})

    @patch(
        'amuse.services.usermanagement.signup_flows.royalty_invitation_flow.split_accepted'
    )
    @patch.object(Common, 'send_signup_completed_event')
    @patch('amuse.tasks.zendesk_create_or_update_user')
    def test_post_registration(
        self, _, mock_send_signup_completed_event, mock_split_accepted
    ):
        user = UserFactory()
        inviter = UserFactory()
        song = SongFactory()
        split = RoyaltySplitFactory(song=song, user=inviter, rate=Decimal('1'))
        token = '123'
        invite = RoyaltyInvitationFactory(
            inviter=inviter,
            token=token,
            status=RoyaltyInvitation.STATUS_PENDING,
            royalty_split=split,
            last_sent=timezone.now(),
        )
        request = APIRequestFactory().post('/users')

        flow = RoyaltyInvitationFlow(token)
        flow.invite = invite
        flow.post_registration(request, user, {})

        invite.refresh_from_db()
        split.refresh_from_db()
        self.assertEqual(invite.status, RoyaltyInvitation.STATUS_ACCEPTED)
        self.assertEqual(invite.invitee.pk, user.pk)

        self.assertEqual(split.status, RoyaltySplit.STATUS_ACTIVE)
        self.assertEqual(split.user_id, user.pk)

        mock_send_signup_completed_event.assert_called_once_with(
            request, user, 'invite'
        )
        mock_split_accepted.assert_called_once_with(split)
