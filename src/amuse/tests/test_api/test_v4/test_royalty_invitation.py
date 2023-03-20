import datetime
from decimal import Decimal
from unittest.mock import patch

import responses
from django.urls import reverse_lazy as reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.exceptions import ErrorDetail

from amuse.tests.test_api.base import API_V4_ACCEPT_VALUE, AmuseAPITestCase
from releases.models import RoyaltySplit
from releases.tests.factories import (
    RoyaltySplitFactory,
    SongFactory,
    ReleaseFactory,
    ReleaseArtistRoleFactory,
)
from users.models.royalty_invitation import RoyaltyInvitation
from users.tests.factories import Artistv2Factory, UserFactory, RoyaltyInvitationFactory


class RoyaltyInvitationAPIV4TestCase(AmuseAPITestCase):
    def setUp(self):
        super().setUp()

        self.user = UserFactory()
        self.release = ReleaseFactory(user=self.user)
        self.song = SongFactory(release=self.release)
        artist = Artistv2Factory(owner=self.user)
        ReleaseArtistRoleFactory(
            artist=artist, release=self.release, main_primary_artist=True
        )
        self.client.credentials(HTTP_ACCEPT=API_V4_ACCEPT_VALUE)
        self.client.force_authenticate(user=self.user)

        self.royalty_split_data = {
            'song': self.song,
            'rate': 1.0,
            'start_date': datetime.date.today(),
        }

        self.invitation = RoyaltyInvitationFactory(
            inviter=UserFactory(artist_name="Elmer Fudd"),
            invitee=self.user,
            token="123",
            status=RoyaltyInvitation.STATUS_PENDING,
            royalty_split=RoyaltySplitFactory(**self.royalty_split_data),
            last_sent=timezone.now(),
        )

        self.invalid_token_errors = [
            ErrorDetail(string='invalid token', code='invalid')
        ]

    @responses.activate
    @patch('amuse.api.base.viewsets.royalty_invitation.split_accepted')
    def test_activate_confirmed_royalty_splits(self, mocked_segment):
        url = reverse("royaltyinvitation-confirm")

        self.invitation.royalty_split.rate = Decimal("0.5")
        self.invitation.royalty_split.save()
        RoyaltySplitFactory(
            song=self.invitation.royalty_split.song,
            rate=Decimal("0.5"),
            revision=1,
            status=RoyaltySplit.STATUS_CONFIRMED,
        )
        data = {"token": "123"}
        response = self.client.post(url, data, format='json')
        self.assertEqual(status.HTTP_202_ACCEPTED, response.status_code, response.data)

        self.invitation.refresh_from_db()
        splits = RoyaltySplit.objects.filter(
            revision=1, status=RoyaltySplit.STATUS_ACTIVE
        )
        self.assertEqual(splits.count(), 2)
        self.assertEqual(splits[0].rate + splits[1].rate, Decimal("1.0"))
        self.assertEqual(self.invitation.status, RoyaltyInvitation.STATUS_ACCEPTED)
        mocked_segment.assert_called_once_with(self.invitation.royalty_split)

    @responses.activate
    def test_does_not_activate_other_status_royalty_splits(self):
        url = reverse("royaltyinvitation-confirm")

        self.invitation.royalty_split.rate = Decimal("0.5")
        self.invitation.royalty_split.save()
        pending_split = RoyaltySplitFactory(
            song=self.invitation.royalty_split.song,
            rate=Decimal("0.5"),
            revision=1,
            status=RoyaltySplit.STATUS_PENDING,
        )
        data = {"token": "123"}
        response = self.client.post(url, data, format='json')
        self.assertEqual(status.HTTP_202_ACCEPTED, response.status_code, response.data)

        pending_split.refresh_from_db()
        self.invitation.refresh_from_db()
        self.invitation.royalty_split.refresh_from_db()

        self.assertEqual(pending_split.status, RoyaltySplit.STATUS_PENDING)
        self.assertEqual(
            self.invitation.royalty_split.status, RoyaltySplit.STATUS_CONFIRMED
        )
        self.assertEqual(self.invitation.status, RoyaltyInvitation.STATUS_ACCEPTED)
        self.assertEqual(
            pending_split.rate + self.invitation.royalty_split.rate, Decimal("1.0")
        )

    @responses.activate
    @patch('amuse.api.base.viewsets.royalty_invitation.split_accepted')
    def test_consolidates_same_owner_splits(self, mocked_segment):
        url = reverse("royaltyinvitation-confirm")

        self.invitation.royalty_split.rate = Decimal("0.5")
        self.invitation.royalty_split.save()

        RoyaltySplitFactory(
            song=self.invitation.royalty_split.song,
            rate=Decimal("0.3"),
            revision=1,
            status=RoyaltySplit.STATUS_CONFIRMED,
            is_owner=False,
        )
        RoyaltySplitFactory(
            user=self.user,
            song=self.invitation.royalty_split.song,
            rate=Decimal("0.1"),
            revision=1,
            status=RoyaltySplit.STATUS_CONFIRMED,
            is_owner=True,
        )
        RoyaltySplitFactory(
            user=self.user,
            song=self.invitation.royalty_split.song,
            rate=Decimal("0.1"),
            revision=1,
            status=RoyaltySplit.STATUS_CONFIRMED,
            is_owner=True,
        )
        data = {"token": "123"}
        response = self.client.post(url, data, format='json')
        self.assertEqual(status.HTTP_202_ACCEPTED, response.status_code, response.data)

        self.invitation.refresh_from_db()
        splits = RoyaltySplit.objects.filter(
            revision=1, status=RoyaltySplit.STATUS_ACTIVE
        )
        self.assertEqual(splits.count(), 2)
        self.assertEqual(splits[0].rate + splits[1].rate, Decimal("1.0"))
        self.assertEqual(self.invitation.status, RoyaltyInvitation.STATUS_ACCEPTED)
        mocked_segment.assert_called_once_with(self.invitation.royalty_split)

        user_split = splits.get(user=self.user)
        self.assertEqual(user_split.rate, Decimal("0.7"))
        self.assertTrue(user_split.is_owner)

    @responses.activate
    @patch('amuse.api.base.viewsets.royalty_invitation.split_accepted')
    def test_consolidates_same_non_owner_splits(self, mocked_segment):
        url = reverse("royaltyinvitation-confirm")
        user2 = UserFactory()
        self.client.force_authenticate(user=user2)

        self.invitation.royalty_split.rate = Decimal("0.5")
        self.invitation.royalty_split.save()

        RoyaltySplitFactory(
            user=self.user,
            song=self.invitation.royalty_split.song,
            rate=Decimal("0.3"),
            revision=1,
            status=RoyaltySplit.STATUS_CONFIRMED,
            is_owner=True,
        )
        RoyaltySplitFactory(
            user=user2,
            song=self.invitation.royalty_split.song,
            rate=Decimal("0.1"),
            revision=1,
            status=RoyaltySplit.STATUS_CONFIRMED,
            is_owner=False,
        )
        RoyaltySplitFactory(
            user=user2,
            song=self.invitation.royalty_split.song,
            rate=Decimal("0.1"),
            revision=1,
            status=RoyaltySplit.STATUS_CONFIRMED,
            is_owner=False,
        )
        data = {"token": "123"}
        response = self.client.post(url, data, format='json')
        self.assertEqual(status.HTTP_202_ACCEPTED, response.status_code, response.data)

        self.invitation.refresh_from_db()
        splits = RoyaltySplit.objects.filter(
            revision=1, status=RoyaltySplit.STATUS_ACTIVE
        )
        self.assertEqual(splits.count(), 2)
        self.assertEqual(splits[0].rate + splits[1].rate, Decimal("1.0"))
        self.assertEqual(self.invitation.status, RoyaltyInvitation.STATUS_ACCEPTED)
        mocked_segment.assert_called_once_with(self.invitation.royalty_split)

        user_split = splits.get(user=user2)
        self.assertEqual(user_split.rate, Decimal("0.7"))
        self.assertFalse(user_split.is_owner)

    def test_confirm_token_success(self):
        url = reverse('royaltyinvitation-confirm')

        data = {'token': "123"}
        response = self.client.post(url, data, format='json')
        self.assertEqual(status.HTTP_202_ACCEPTED, response.status_code, response.data)

    @responses.activate
    def test_confirm_token_invalid_token(self):
        url = reverse('royaltyinvitation-confirm')

        response = self.client.post(url, {'token': 'invalid_token_123'}, format='json')
        self.assertEqual(status.HTTP_404_NOT_FOUND, response.status_code)

    @responses.activate
    def test_confirm_token_invalid_status_created(self):
        url = reverse('royaltyinvitation-confirm')

        self.invitation.status = RoyaltyInvitation.STATUS_CREATED
        self.invitation.save()

        response = self.client.post(url, {'token': '123'}, format='json')
        self.assertEqual(status.HTTP_400_BAD_REQUEST, response.status_code)
        self.assertListEqual(self.invalid_token_errors, response.data)

    @responses.activate
    def test_confirm_token_invalid_status_accepted(self):
        url = reverse('royaltyinvitation-confirm')

        self.invitation.status = RoyaltyInvitation.STATUS_ACCEPTED
        self.invitation.save()

        response = self.client.post(url, {'token': '123'}, format='json')
        self.assertEqual(status.HTTP_400_BAD_REQUEST, response.status_code)
        self.assertListEqual(self.invalid_token_errors, response.data)

    @responses.activate
    def test_confirm_token_invalid_status_declined(self):
        url = reverse('royaltyinvitation-confirm')

        self.invitation.status = RoyaltyInvitation.STATUS_DECLINED
        self.invitation.save()

        response = self.client.post(url, {'token': '123'}, format='json')
        self.assertEqual(status.HTTP_400_BAD_REQUEST, response.status_code)
        self.assertListEqual(self.invalid_token_errors, response.data)

    @responses.activate
    def test_confirm_token_invalid_status_expired(self):
        url = reverse('royaltyinvitation-confirm')

        self.invitation.last_sent = timezone.now() - datetime.timedelta(days=31)
        self.invitation.save()
        response = self.client.post(url, {'token': '123'}, format='json')
        self.assertEqual(status.HTTP_400_BAD_REQUEST, response.status_code)

    @responses.activate
    def test_confirm_token_invalid_status_not_sent(self):
        url = reverse('royaltyinvitation-confirm')

        self.invitation.last_sent = None
        self.invitation.save()
        response = self.client.post(url, {'token': '123'}, format='json')
        self.assertEqual(status.HTTP_400_BAD_REQUEST, response.status_code)
