from datetime import date
from decimal import Decimal
from unittest.mock import patch, Mock
from unittest import skip

import pytest
import responses
from flaky import flaky
from freezegun import freeze_time
from django.test import TestCase, override_settings
from django.utils import timezone
from amuse.vendor.customerio.events import CustomerIOEvents, default as cioevents

from amuse.tests.helpers import (
    add_zendesk_mock_post_response,
    ZENDESK_MOCK_API_URL_TOKEN,
)

from amuse.api.v4.serializers.helpers import (
    create_song_artists_roles,
    create_royalty_splits,
    update_royalty_splits,
    update_splits_state,
    create_invite,
    create_song_artist_invites,
    fetch_spotify_image,
    is_valid_split_for_free_user,
    notify_release_owner_if_required,
    RoyaltySplitFirstRevisionExistsError,
    get_split_start_date,
    create_revision_of_royalty_splits,
)
from releases.models import ReleaseArtistRole
from releases.models.song import SongArtistRole
from releases.models.royalty_split import RoyaltySplit
from releases.tests.factories import (
    ReleaseArtistRoleFactory,
    ReleaseFactory,
    SongFactory,
    RoyaltySplitFactory,
)
from users.models.royalty_invitation import RoyaltyInvitation
from users.models.song_artist_invitation import SongArtistInvitation
from users.tests.factories import UserFactory, Artistv2Factory, UserArtistRoleFactory
from users.models import UserArtistRole


@override_settings(**ZENDESK_MOCK_API_URL_TOKEN)
class TestSerializerHelpers(TestCase):
    @responses.activate
    def setUp(self):
        add_zendesk_mock_post_response()
        self.user = UserFactory()
        self.user.create_artist_v2(name=self.user.artist_name)
        self.release = ReleaseFactory(user=self.user)
        self.artist = self.user.artists.first()
        self.song = SongFactory(release=self.release)
        ReleaseArtistRoleFactory(
            artist=self.artist,
            release=self.release,
            role=ReleaseArtistRole.ROLE_PRIMARY_ARTIST,
            main_primary_artist=True,
        )

    @responses.activate
    def test_create_royalty_splits(self):
        add_zendesk_mock_post_response()
        user_2 = UserFactory()

        invite = {
            "email": "artist@example.com",
            "phone_number": "+46712345678",
            "name": "Artist Name",
        }
        royalty_splits = [
            {'user_id': self.user.id, 'rate': Decimal(0.5)},
            {'user_id': user_2.id, 'rate': Decimal(0.5)},
        ]

        create_royalty_splits(self.user, self.song, royalty_splits)

        for royalty_split in royalty_splits:
            user_id = royalty_split['user_id']
            rate = royalty_split['rate']
            # Make sure a RoyaltySplit is created
            self.assertTrue(
                RoyaltySplit.objects.filter(
                    song=self.song, user_id=user_id, rate=rate, revision=1
                ).exists()
            )

            # Make sure a RoyaltySplit created only one instance
            self.assertEqual(
                RoyaltySplit.objects.filter(
                    song=self.song, user_id=user_id, rate=rate, revision=1
                ).count(),
                1,
            )

        splits = RoyaltySplit.objects.all()
        self.assertEqual(splits.count(), 2)
        self.assertEqual(splits[0].status, RoyaltySplit.STATUS_CONFIRMED)
        self.assertEqual(splits[1].status, RoyaltySplit.STATUS_PENDING)
        self.assertEqual(splits[0].start_date, None)
        self.assertEqual(splits[1].start_date, None)

    @responses.activate
    def test_create_royalty_splits_raises_error_on_update(self):
        add_zendesk_mock_post_response()
        user_2 = UserFactory()

        invite = {
            "email": "artist@example.com",
            "phone_number": "+46712345678",
            "name": "Artist Name",
        }
        royalty_splits = [
            {'user_id': self.user.id, 'rate': Decimal(0.5)},
            {'user_id': user_2.id, 'rate': Decimal(0.5)},
        ]

        create_royalty_splits(self.user, self.song, royalty_splits)

        royalty_splits = [
            {'user_id': self.user.id, 'rate': Decimal(0.5)},
            {'user_id': user_2.id, 'rate': Decimal(0.25)},
            {'user_id': None, 'invite': invite, 'rate': Decimal(0.25)},
        ]

        with pytest.raises(RoyaltySplitFirstRevisionExistsError):
            create_royalty_splits(self.user, self.song, royalty_splits)

    @responses.activate
    def test_create_royalty_splits_single_existing_user_get_active_status(self):
        add_zendesk_mock_post_response()

        royalty_splits = [{'user_id': self.user.id, 'rate': Decimal(1.0)}]

        create_royalty_splits(self.user, self.song, royalty_splits)

        user_id = royalty_splits[0]['user_id']
        rate = royalty_splits[0]['rate']
        # Make sure a RoyaltySplit is created
        self.assertTrue(
            RoyaltySplit.objects.filter(
                song=self.song,
                user_id=user_id,
                rate=rate,
                revision=1,
                status=RoyaltySplit.STATUS_ACTIVE,
            ).exists()
        )

    @responses.activate
    def test_create_royalty_splits_invited_users_get_pending_status(self):
        add_zendesk_mock_post_response()

        invitee_email = "artist@example.com"
        invitee_name = "Artist Name"
        invitee_phone_number = "+46712345678"

        invite = {
            "email": invitee_email,
            "phone_number": invitee_phone_number,
            "name": invitee_name,
        }

        royalty_splits = [{'user_id': None, 'invite': invite, 'rate': Decimal(1.0)}]

        create_royalty_splits(self.user, self.song, royalty_splits)

        split = RoyaltySplit.objects.get()
        self.assertEqual(split.status, RoyaltySplit.STATUS_PENDING)

    @responses.activate
    def test_create_royalty_splits_mixed_statuses_works_as_expected(self):
        add_zendesk_mock_post_response()
        user_2 = UserFactory()

        invitee_email = "artist@example.com"
        invitee_name = "Artist Name"
        invitee_phone_number = "+46712345678"

        invite = {
            "email": invitee_email,
            "phone_number": invitee_phone_number,
            "name": invitee_name,
        }

        royalty_splits = [
            {'user_id': self.user.id, 'rate': Decimal(0.5)},
            {'user_id': user_2.id, 'rate': Decimal(0.25)},
            {'user_id': None, 'invite': invite, 'rate': Decimal(0.25)},
        ]

        create_royalty_splits(self.user, self.song, royalty_splits)

        invite_split = RoyaltySplit.objects.get(user__isnull=True)
        self.assertEqual(invite_split.status, RoyaltySplit.STATUS_PENDING)

        existing_user_splits = RoyaltySplit.objects.filter(user__isnull=False)
        self.assertEqual(existing_user_splits[0].status, RoyaltySplit.STATUS_CONFIRMED)
        self.assertEqual(existing_user_splits[1].status, RoyaltySplit.STATUS_PENDING)

    @responses.activate
    def test_create_royalty_splits_and_invites_when_user_id_is_not_provided(self):
        invitee_email = "artist@example.com"
        invitee_name = "Artist Name"
        invitee_phone_number = "+46712345678"

        invite = {
            "email": invitee_email,
            "phone_number": invitee_phone_number,
            "name": invitee_name,
        }
        rate = Decimal(1.0)

        royalty_splits = [{'user_id': None, 'invite': invite, 'rate': rate}]

        create_royalty_splits(self.user, self.song, royalty_splits)

        # Make sure a RoyaltySplit is created
        self.assertTrue(
            RoyaltySplit.objects.filter(song=self.song, rate=rate, revision=1).exists()
        )

        # Make sure a RoyaltySplit created only one instance
        self.assertEqual(
            RoyaltySplit.objects.filter(song=self.song, rate=rate, revision=1).count(),
            1,
        )
        # Make sure a RoyaltyInvitation is created
        self.assertTrue(
            RoyaltyInvitation.objects.filter(
                inviter=self.user,
                email=invitee_email,
                phone_number=invitee_phone_number,
                name=invitee_name,
            ).exists()
        )

        # Make sure a RoyaltyInvitation created only one instance
        self.assertEqual(
            RoyaltyInvitation.objects.filter(
                inviter=self.user,
                email=invitee_email,
                phone_number=invitee_phone_number,
                name=invitee_name,
            ).count(),
            1,
        )

    @skip("Skip until cio issue is resolved")
    @responses.activate
    @patch.object(CustomerIOEvents, 'send_royalty_invite', autospec=True)
    @patch("amuse.api.v4.serializers.helpers.update_splits_state")
    def test_update_royalty_splits(self, mocked_update_splits_state, mocked_cioevents):
        RoyaltySplitFactory(
            song=self.song,
            user=self.user,
            rate=Decimal("1.00"),
            status=RoyaltySplit.STATUS_ACTIVE,
            revision=1,
        )
        invitee_email = "artist@example.com"
        invitee_name = "Artist Name"
        invitee_phone_number = "+46712345678"

        invite = {
            "email": invitee_email,
            "phone_number": invitee_phone_number,
            "name": invitee_name,
        }

        royalty_splits = [{'user_id': None, 'invite': invite, 'rate': Decimal("1.00")}]
        update_royalty_splits(self.user, self.song, royalty_splits)

        # token = user_invitation_token_generator.make_token({
        #     'inviter_id': self.song.release.user.id,
        #     'invitee_id': 1,
        #     'artist_name': "kljuk",
        #     'split_id': 1,
        # })
        # with mock.patch.object(
        #     user_invitation_token_generator, 'make_token', return_value=token
        # ):

        splits = RoyaltySplit.objects.all()
        self.assertEqual(splits.count(), 2)

        new_split = splits.get(revision=2)

        self.assertEqual(new_split.start_date, timezone.now().today().date())
        self.assertEqual(new_split.status, RoyaltySplit.STATUS_PENDING)

        mocked_update_splits_state.assert_called_once()

        invitation = RoyaltyInvitation.objects.filter(royalty_split=new_split).first()
        cio_payload = {
            'inviter_id': self.user.id,
            'invitee_id': None,
            'invitee_name': invitee_name,
            'inviter_first_name': self.user.first_name,
            'inviter_last_name': self.user.last_name,
            'token': invitation.token,
            'song_name': self.song.name,
            'release_date': self.song.release.release_date,
            'royalty_rate': '100.00%',
            'expiration_time': invitation.expiration_time.strftime("%m/%d/%Y, %H:%M"),
        }
        mocked_cioevents.assert_called_once_with(
            cioevents(), invitee_email, invitee_phone_number, cio_payload
        )

        invitations = RoyaltyInvitation.objects.all()
        self.assertEqual(invitations.count(), 1)

        invitation = invitations[0]

        self.assertEqual(invitation.status, RoyaltyInvitation.STATUS_PENDING)
        self.assertTrue(invitation.last_sent)
        self.assertTrue(invitation.token)
        self.assertIsInstance(invitation.token, str)

    @responses.activate
    def test_update_confirmed_splits_works_with_revision_1_active(self):
        add_zendesk_mock_post_response()
        user2 = UserFactory()

        RoyaltySplitFactory(
            song=self.song,
            user=self.user,
            rate=Decimal("0.50"),
            status=RoyaltySplit.STATUS_ACTIVE,
            revision=1,
        )
        RoyaltySplitFactory(
            song=self.song,
            user=user2,
            rate=Decimal("0.50"),
            status=RoyaltySplit.STATUS_ACTIVE,
            revision=1,
        )
        splits = RoyaltySplit.objects.all()
        update_splits_state(self.song, 1)

        self.assertQuerysetEqual(
            splits, RoyaltySplit.objects.all(), transform=lambda x: x, ordered=False
        )

    @responses.activate
    def test_update_confirmed_splits_works_with_revision_1_confirmed(self):
        add_zendesk_mock_post_response()
        user2 = UserFactory()

        RoyaltySplitFactory(
            song=self.song,
            user=self.user,
            rate=Decimal("0.50"),
            status=RoyaltySplit.STATUS_CONFIRMED,
            revision=1,
        )
        RoyaltySplitFactory(
            song=self.song,
            user=user2,
            rate=Decimal("0.50"),
            status=RoyaltySplit.STATUS_CONFIRMED,
            revision=1,
        )
        splits = RoyaltySplit.objects.all()
        update_splits_state(self.song, 1)

        updated_splits = RoyaltySplit.objects.all()
        self.assertEqual(updated_splits[0].status, RoyaltySplit.STATUS_ACTIVE)
        self.assertEqual(updated_splits[1].status, RoyaltySplit.STATUS_ACTIVE)

    @responses.activate
    def test_update_confirmed_splits_works_with_revision_1_inactive(self):
        RoyaltySplitFactory(
            song=self.song,
            user=self.user,
            rate=Decimal("0.50"),
            status=RoyaltySplit.STATUS_CONFIRMED,
            revision=1,
        )
        RoyaltySplitFactory(
            song=self.song,
            user=None,
            rate=Decimal("0.50"),
            status=RoyaltySplit.STATUS_PENDING,
            revision=1,
        )
        splits = RoyaltySplit.objects.all()
        update_splits_state(self.song, 1)

        self.assertQuerysetEqual(
            splits, RoyaltySplit.objects.all(), transform=lambda x: x, ordered=False
        )

    @responses.activate
    def test_update_confirmed_splits_works_with_revision_2_confirmed(self):
        add_zendesk_mock_post_response()
        user2 = UserFactory()

        RoyaltySplitFactory(
            song=self.song,
            user=self.user,
            rate=Decimal("1.00"),
            status=RoyaltySplit.STATUS_ACTIVE,
            revision=1,
        )
        RoyaltySplitFactory(
            song=self.song,
            user=self.user,
            rate=Decimal("0.50"),
            status=RoyaltySplit.STATUS_CONFIRMED,
            revision=2,
        )
        RoyaltySplitFactory(
            song=self.song,
            user=user2,
            rate=Decimal("0.50"),
            status=RoyaltySplit.STATUS_CONFIRMED,
            revision=2,
        )
        update_splits_state(self.song, 2)

        updated_splits = RoyaltySplit.objects.all()
        self.assertEqual(updated_splits[0].status, RoyaltySplit.STATUS_ARCHIVED)
        self.assertEqual(updated_splits[1].status, RoyaltySplit.STATUS_ACTIVE)
        self.assertEqual(updated_splits[2].status, RoyaltySplit.STATUS_ACTIVE)
        self.assertEqual(updated_splits[0].revision, 1)
        self.assertEqual(updated_splits[1].revision, 2)
        self.assertEqual(updated_splits[2].revision, 2)

    @responses.activate
    @flaky(max_runs=3)
    def test_update_confirmed_splits_works_with_revision_3_confirmed(self):
        add_zendesk_mock_post_response()

        RoyaltySplitFactory(
            song=self.song,
            user=self.user,
            rate=Decimal("1.00"),
            status=RoyaltySplit.STATUS_ACTIVE,
            start_date=None,
            end_date=None,
            revision=1,
        )
        RoyaltySplitFactory(
            song=self.song,
            user=None,
            rate=Decimal("1.00"),
            status=RoyaltySplit.STATUS_PENDING,
            start_date=date(2020, 1, 15),
            end_date=None,
            revision=2,
        )

        with freeze_time("2020-01-20"):
            user2 = UserFactory(is_pro=True)
            RoyaltySplitFactory(
                song=self.song,
                user=self.user,
                rate=Decimal("0.50"),
                status=RoyaltySplit.STATUS_CONFIRMED,
                start_date=date(2020, 1, 15),
                end_date=None,
                revision=3,
            )
            RoyaltySplitFactory(
                song=self.song,
                user=user2,
                rate=Decimal("0.50"),
                status=RoyaltySplit.STATUS_CONFIRMED,
                start_date=date(2020, 1, 15),
                end_date=None,
                revision=3,
            )
            update_splits_state(self.song, 3)

        updated_splits = RoyaltySplit.objects.all()
        self.assertEqual(updated_splits.count(), 3)
        self.assertEqual(updated_splits[0].status, RoyaltySplit.STATUS_ARCHIVED)
        self.assertEqual(updated_splits[1].status, RoyaltySplit.STATUS_ACTIVE)
        self.assertEqual(updated_splits[2].status, RoyaltySplit.STATUS_ACTIVE)
        self.assertEqual(updated_splits[0].revision, 1)
        self.assertEqual(updated_splits[1].revision, 2)
        self.assertEqual(updated_splits[2].revision, 2)

    @responses.activate
    def test_update_confirmed_splits_replaces_same_day_active_2nd_revision_splits(self):
        with freeze_time("2020-01-01"):
            RoyaltySplitFactory(
                user=self.user,
                song=self.song,
                rate=Decimal("1.00"),
                start_date=None,
                end_date=date(2020, 1, 14),
                status=RoyaltySplit.STATUS_ARCHIVED,
                revision=1,
            )
        with freeze_time("2020-01-15"):
            RoyaltySplitFactory(
                user=self.user,
                song=self.song,
                rate=Decimal("1.00"),
                start_date=timezone.now().today(),
                end_date=None,
                status=RoyaltySplit.STATUS_ACTIVE,
                revision=2,
            )
            RoyaltySplitFactory(
                user=self.user,
                song=self.song,
                rate=Decimal("1.00"),
                start_date=timezone.now().today(),
                end_date=None,
                status=RoyaltySplit.STATUS_CONFIRMED,
                revision=3,
            )

            update_splits_state(self.song, 3)

        splits = RoyaltySplit.objects.all()
        self.assertEqual(splits.count(), 2)

        old_split = splits.get(revision=1)
        new_split = splits.get(revision=2)

        self.assertEqual(old_split.start_date, None)
        self.assertEqual(old_split.end_date, date(2020, 1, 14))
        self.assertEqual(old_split.status, RoyaltySplit.STATUS_ARCHIVED)
        self.assertEqual(old_split.revision, 1)

        self.assertEqual(new_split.start_date, date(2020, 1, 15))
        self.assertEqual(new_split.end_date, None)
        self.assertEqual(new_split.status, RoyaltySplit.STATUS_ACTIVE)
        self.assertEqual(new_split.revision, 2)

    @responses.activate
    def test_update_confirmed_splits_sets_correct_dates_for_one_day_splits(self):
        with freeze_time("2020-01-05"):
            split_1 = RoyaltySplitFactory(
                song=self.song,
                user=self.user,
                rate=Decimal("1.00"),
                start_date=None,
                end_date=None,
                status=RoyaltySplit.STATUS_ACTIVE,
                revision=1,
            )
        with freeze_time("2020-01-06"):
            split_2 = RoyaltySplitFactory(
                song=self.song,
                user=self.user,
                rate=Decimal("1.00"),
                start_date=date.today(),
                end_date=None,
                status=RoyaltySplit.STATUS_CONFIRMED,
                revision=2,
            )
            update_splits_state(self.song, 2)

        splits = RoyaltySplit.objects.all()
        self.assertEqual(splits.count(), 2)

        updated_split_1 = splits.get(id=split_1.id)
        updated_split_2 = splits.get(id=split_2.id)

        self.assertEqual(updated_split_1.status, RoyaltySplit.STATUS_ARCHIVED)
        self.assertEqual(updated_split_1.start_date, None)
        self.assertEqual(updated_split_1.end_date, date(2020, 1, 5))
        self.assertEqual(updated_split_2.status, RoyaltySplit.STATUS_ACTIVE)
        self.assertEqual(updated_split_2.start_date, date(2020, 1, 6))
        self.assertEqual(updated_split_2.end_date, None)

        with freeze_time("2020-01-07"):
            split_3 = RoyaltySplitFactory(
                song=self.song,
                user=self.user,
                rate=Decimal("1.00"),
                start_date=date.today(),
                end_date=None,
                status=RoyaltySplit.STATUS_CONFIRMED,
                revision=3,
            )
            update_splits_state(self.song, 3)

        splits = RoyaltySplit.objects.all()
        self.assertEqual(splits.count(), 3)

        updated_split_2 = splits.get(id=split_2.id)
        updated_split_3 = splits.get(id=split_3.id)

        self.assertEqual(updated_split_2.status, RoyaltySplit.STATUS_ARCHIVED)
        self.assertEqual(updated_split_2.start_date, date(2020, 1, 6))
        self.assertEqual(updated_split_2.end_date, date(2020, 1, 6))
        self.assertEqual(updated_split_3.status, RoyaltySplit.STATUS_ACTIVE)
        self.assertEqual(updated_split_3.start_date, date(2020, 1, 7))
        self.assertEqual(updated_split_3.end_date, None)

    @responses.activate
    @patch('amuse.api.v4.serializers.helpers.RoyaltyInvitation')
    def test_create_invite(self, MockedRoyaltyInvitation):
        invitee_email = "artist@example.com"
        invitee_name = "Artist Name"
        invitee_phone_number = "+46712345678"

        invite = {
            "email": invitee_email,
            "phone_number": invitee_phone_number,
            "name": invitee_name,
        }

        royalty_split = Mock()
        create_invite(self.song, self.user, None, royalty_split, invite)
        MockedRoyaltyInvitation.objects.create.assert_called_once_with(
            inviter=self.user,
            invitee=None,
            royalty_split=royalty_split,
            email=invitee_email,
            name=invitee_name,
            phone_number=invitee_phone_number,
            token=None,
        )

    @responses.activate
    def test_create_song_artist_invites(self):
        add_zendesk_mock_post_response()
        new_artist = Artistv2Factory(name='InviteMe')
        invites_list = [
            {
                'artist_id': new_artist.id,
                'email': 'test@example.com',
                'phone_number': '+46712345678',
            }
        ]
        create_song_artist_invites(self.user, self.song, invites_list)
        invite = SongArtistInvitation.objects.get(song=self.song)
        self.assertEqual(invite.status, SongArtistInvitation.STATUS_CREATED)
        self.assertEqual(invite.email, 'test@example.com')
        self.assertEqual(invite.phone_number, '+46712345678')

    @responses.activate
    @patch('amuse.vendor.spotify.spotify_api.SpotifyAPI.fetch_spotify_artist_image_url')
    def test_fetch_spotify_image(self, mock_spotify):
        add_zendesk_mock_post_response()

        image_url = fetch_spotify_image(spotify_id=None, default_image_url=None)
        self.assertIsNone(image_url)

        mock_spotify.return_value = None
        image_url = fetch_spotify_image(
            spotify_id="123", default_image_url="original_url"
        )
        self.assertEqual("original_url", image_url)

        mock_spotify.return_value = "spotify_url"
        image_url = fetch_spotify_image(
            spotify_id="123", default_image_url="original_url"
        )
        self.assertEqual("spotify_url", image_url)

    def test_is_valid_split_for_free_user_returns_true_when_valid(self):
        owner_id = 1
        splits = [{'user_id': owner_id, 'rate': Decimal('1.0'), 'invite': None}]
        self.assertTrue(is_valid_split_for_free_user(splits, owner_id))

    def test_is_valid_split_for_free_user_returns_false_when_user_in_not_owner(self):
        owner_id = 1
        another_user_id = 2
        splits = [{'user_id': another_user_id, 'rate': Decimal('1.0'), 'invite': None}]
        self.assertFalse(is_valid_split_for_free_user(splits, owner_id))

    def test_is_valid_split_for_free_user_returns_false_when_its_more_then_one_split(
        self,
    ):
        owner_id = 1
        another_user_id = 2
        splits = [
            {'user_id': owner_id, 'rate': Decimal('0.5'), 'invite': None},
            {'user_id': another_user_id, 'rate': Decimal('0.5'), 'invite': None},
        ]
        self.assertFalse(is_valid_split_for_free_user(splits, owner_id))

    def test_is_valid_split_for_free_user_returns_false_when_rate_is_not_equal_1(self):
        owner_id = 1
        splits = [{'user_id': owner_id, 'rate': Decimal('0.5'), 'invite': None}]
        self.assertFalse(is_valid_split_for_free_user(splits, owner_id))

    def test_get_splits_start_date_returns_start_date(self):
        split = RoyaltySplitFactory(
            song=self.song, user=self.user, start_date=date(2020, 1, 1)
        )
        self.assertEqual(get_split_start_date(split, self.release), split.start_date)

    def test_get_splits_start_date_returns_created_date(self):
        split = RoyaltySplitFactory(song=self.song, user=self.user, start_date=None)
        self.release.created = date(2019, 12, 1)
        self.release.save()
        self.release.refresh_from_db()
        self.assertEqual(
            get_split_start_date(split, self.release), self.release.created
        )

    def test_get_splits_start_date_returns_original_release_date(self):
        split = RoyaltySplitFactory(song=self.song, user=self.user, start_date=None)
        self.release.created = date(2019, 12, 1)
        self.release.original_release_date = date(2019, 11, 1)
        self.release.save()
        self.release.refresh_from_db()
        self.assertEqual(
            get_split_start_date(split, self.release),
            self.release.original_release_date,
        )


@override_settings(**ZENDESK_MOCK_API_URL_TOKEN)
class TestSendingRoyaltyInviteToTheOwner(TestCase):
    @responses.activate
    @patch('amuse.api.v4.serializers.helpers.create_invite', autospec=True)
    def test_do_not_send_invite_to_the_owner(self, mock_create_invite):
        add_zendesk_mock_post_response()

        owner = UserFactory()
        inviter = UserFactory()
        royalty_splits = [
            {"rate": 0.2, "user_id": owner.id},
            {"rate": 0.2, "user_id": inviter.id},
            {"rate": 0.6, "invite": {"email": "email@email.email", "name": "john"}},
        ]
        release = ReleaseFactory(user=owner)
        song = SongFactory(release=release)
        artist = owner.create_artist_v2(name='Artist Name')
        ReleaseArtistRoleFactory(
            artist=artist,
            release=release,
            role=ReleaseArtistRole.ROLE_PRIMARY_ARTIST,
            main_primary_artist=True,
        )

        args = {
            'inviter': inviter,
            'song': song,
            'royalty_splits': royalty_splits,
            'start_date': timezone.now(),
            'revision': 1,
        }

        create_revision_of_royalty_splits(args, send_invite=True)
        mock_create_invite.assert_called_once()


@override_settings(**ZENDESK_MOCK_API_URL_TOKEN)
class TestNotifyReleaseOwnerIfRequired(TestCase):
    @responses.activate
    @patch('amuse.tasks.send_royalty_owner_notification_email.delay', autospec=True)
    def test_do_not_notify_if_owner_is_inviter(self, mock_delay):
        add_zendesk_mock_post_response()
        owner = UserFactory()
        song = SongFactory()
        artist = Artistv2Factory()

        RoyaltySplitFactory(song=song, user=owner, rate=Decimal(1.0))
        UserArtistRoleFactory(user=owner, artist=artist, type=UserArtistRole.OWNER)

        notify_release_owner_if_required(owner, song, [{'rate': '1.00000'}], artist)
        self.assertEqual(0, mock_delay.call_count)

    @responses.activate
    @patch('amuse.tasks.send_royalty_owner_notification_email.delay', autospec=True)
    def test_do_not_notify_if_rate_is_100_percent(self, mock_delay):
        add_zendesk_mock_post_response()
        song = SongFactory()
        artist = Artistv2Factory()
        owner = UserFactory()
        inviter = UserFactory()

        RoyaltySplitFactory(song=song, user=owner, rate=Decimal(1.0))
        UserArtistRoleFactory(user=owner, artist=artist, type=UserArtistRole.OWNER)

        request_splits = [{'rate': Decimal(1.0000)}]

        notify_release_owner_if_required(inviter, song, request_splits, artist)
        self.assertEqual(0, mock_delay.call_count)

    @responses.activate
    @patch('amuse.tasks.send_royalty_owner_notification_email.delay', autospec=True)
    def test_do_nothing_if_owner_role_is_missing(self, mock_delay):
        add_zendesk_mock_post_response()
        song = SongFactory()
        artist = Artistv2Factory()
        owner = UserFactory()
        inviter = UserFactory()

        RoyaltySplitFactory(song=song, user=owner, rate=Decimal(1.0))

        request_splits = [{'rate': Decimal(1.0000)}]

        notify_release_owner_if_required(inviter, song, request_splits, artist)
        self.assertEqual(0, mock_delay.call_count)

    @responses.activate
    @patch('amuse.tasks.send_royalty_owner_notification_email.delay', autospec=True)
    def test_notify_once_if_there_are_multiple_splits(self, mock_delay):
        add_zendesk_mock_post_response()
        song = SongFactory()
        artist = Artistv2Factory()
        owner = UserFactory()
        inviter = UserFactory()

        RoyaltySplitFactory(song=song, user=owner, rate=Decimal(0.40))
        RoyaltySplitFactory(song=song, user=UserFactory(), rate=Decimal(0.20))
        RoyaltySplitFactory(song=song, user=UserFactory(), rate=Decimal(0.10))
        RoyaltySplitFactory(song=song, user=UserFactory(), rate=Decimal(0.30))

        UserArtistRoleFactory(user=owner, artist=artist, type=UserArtistRole.OWNER)

        request_splits = [
            {'rate': Decimal(0.4)},
            {'rate': Decimal(0.2)},
            {'rate': Decimal(0.1)},
            {'rate': Decimal(0.3)},
        ]

        notify_release_owner_if_required(inviter, song, request_splits, artist)
        mock_delay.assert_called_once_with(
            owner.id,
            owner.get_full_name(),
            song.name,
            inviter.first_name,
            inviter.last_name,
            request_splits[0]['rate'],
        )


@override_settings(**ZENDESK_MOCK_API_URL_TOKEN)
class TestCreateSongArtistRoles(TestCase):
    @responses.activate
    def setUp(self):
        add_zendesk_mock_post_response()
        self.user = UserFactory()
        self.user.create_artist_v2(name=self.user.artist_name)
        self.release = ReleaseFactory(user=self.user)
        self.artist = self.user.artists.first()
        self.song = SongFactory(release=self.release)
        ReleaseArtistRoleFactory(
            artist=self.artist,
            release=self.release,
            role=ReleaseArtistRole.ROLE_PRIMARY_ARTIST,
            main_primary_artist=True,
        )
        self.artist_role_names = [
            role_string_value for _, role_string_value in SongArtistRole.ROLE_CHOICES
        ]

    @responses.activate
    def test_create_song_artists_roles(self):
        add_zendesk_mock_post_response()

        artists_roles_list = [
            {'artist_id': self.artist.id, 'roles': self.artist_role_names}
        ]
        create_song_artists_roles(self.song, artists_roles_list, self.artist.id)

        actual_roles = SongArtistRole.objects.filter(song=self.song, artist=self.artist)
        self.assertEqual(len(artists_roles_list[0]['roles']), len(actual_roles))

        for role_int_value, role_string_value in SongArtistRole.ROLE_CHOICES:
            self.assertEqual(
                1,
                SongArtistRole.objects.filter(
                    song=self.song, artist=self.artist, role=role_int_value
                ).count(),
            )

    @responses.activate
    def test_duplicate_role_names(self):
        add_zendesk_mock_post_response()
        get_role_for_keyword = SongArtistRole.get_role_for_keyword

        role0 = self.artist_role_names[0]
        role1 = self.artist_role_names[1]
        role2 = self.artist_role_names[2]

        # note: 2x role0
        artists_roles_list = [
            {'artist_id': self.artist.id, 'roles': [role0, role1, role2, role0]}
        ]
        create_song_artists_roles(self.song, artists_roles_list, self.artist.id)

        actual_roles = SongArtistRole.objects.filter(song=self.song, artist=self.artist)
        self.assertEqual(3, len(actual_roles))

        self.assertEqual(
            1,
            SongArtistRole.objects.filter(
                song=self.song, artist=self.artist, role=get_role_for_keyword(role0)
            ).count(),
        )

        self.assertEqual(
            1,
            SongArtistRole.objects.filter(
                song=self.song, artist=self.artist, role=get_role_for_keyword(role1)
            ).count(),
        )

        self.assertEqual(
            1,
            SongArtistRole.objects.filter(
                song=self.song, artist=self.artist, role=get_role_for_keyword(role2)
            ).count(),
        )

    @responses.activate
    def test_duplicate_artists(self):
        add_zendesk_mock_post_response()
        get_role_for_keyword = SongArtistRole.get_role_for_keyword

        role0 = self.artist_role_names[0]
        role1 = self.artist_role_names[1]
        role2 = self.artist_role_names[2]

        artist2 = Artistv2Factory()

        # note: 2x same artist
        artists_roles_list = [
            {'artist_id': self.artist.id, 'roles': [role0, role1, role0]},
            {'artist_id': self.artist.id, 'roles': [role2]},
            {'artist_id': artist2.id, 'roles': [role2]},
        ]
        create_song_artists_roles(self.song, artists_roles_list, self.artist.id)

        self.assertEqual(4, SongArtistRole.objects.filter(song=self.song).count())

        self.assertEqual(
            1,
            SongArtistRole.objects.filter(
                song=self.song, artist=self.artist, role=get_role_for_keyword(role0)
            ).count(),
        )

        self.assertEqual(
            1,
            SongArtistRole.objects.filter(
                song=self.song, artist=self.artist, role=get_role_for_keyword(role1)
            ).count(),
        )

        self.assertEqual(
            1,
            SongArtistRole.objects.filter(
                song=self.song, artist=self.artist, role=get_role_for_keyword(role2)
            ).count(),
        )

        self.assertEqual(
            1,
            SongArtistRole.objects.filter(
                song=self.song, artist=artist2, role=get_role_for_keyword(role2)
            ).count(),
        )
