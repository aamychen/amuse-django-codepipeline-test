from datetime import date, timedelta
from decimal import Decimal
from uuid import uuid4

from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone
from unittest.mock import call, patch


from releases.models import Release, RoyaltySplit
from releases.tests.factories import SongFactory, RoyaltySplitFactory, ReleaseFactory
from users.models import RoyaltyInvitation
from users.tests.factories import UserFactory, RoyaltyInvitationFactory

COMMAND = 'cancel_expired_inactive_splits'

CONFIRMED = 1
PENDING = 2
ACTIVE = 3
ARCHIVED = 4

SPLIT_STATUS_MAP = dict()
INVITE_STATUS_MAP = dict()

SPLIT_STATUS_MAP[CONFIRMED] = RoyaltySplit.STATUS_CONFIRMED
SPLIT_STATUS_MAP[PENDING] = RoyaltySplit.STATUS_PENDING
SPLIT_STATUS_MAP[ACTIVE] = RoyaltySplit.STATUS_ACTIVE
SPLIT_STATUS_MAP[ARCHIVED] = RoyaltySplit.STATUS_ARCHIVED

INVITE_STATUS_MAP[CONFIRMED] = RoyaltyInvitation.STATUS_ACCEPTED
INVITE_STATUS_MAP[PENDING] = RoyaltyInvitation.STATUS_PENDING
INVITE_STATUS_MAP[ACTIVE] = RoyaltyInvitation.STATUS_ACCEPTED
INVITE_STATUS_MAP[ARCHIVED] = RoyaltyInvitation.STATUS_ACCEPTED


class NewSplitResult:
    def __init__(self, split, invite):
        self.split = split
        self.invite = invite


def new_split(inviter, song, revision, status, rate, is_owner=False, expired=True):
    split_status = SPLIT_STATUS_MAP[status]
    user = inviter if split_status != RoyaltySplit.STATUS_PENDING else None

    split = RoyaltySplitFactory(
        user=user,
        song=song,
        revision=revision,
        status=split_status,
        rate=Decimal(rate),
        is_owner=is_owner,
        is_locked=False,
    )

    if is_owner:
        return NewSplitResult(split=split, invite=None)

    invite_status = INVITE_STATUS_MAP[status]
    last_sent = timezone.now()

    if expired:
        last_sent = timezone.now() - timedelta(
            days=RoyaltyInvitation.EXPIRATION_DAYS + 1
        )

    invite = RoyaltyInvitationFactory(
        inviter=inviter,
        invitee=None,
        status=invite_status,
        token=str(uuid4()),
        royalty_split=split,
        last_sent=last_sent,
    )

    return NewSplitResult(split=split, invite=invite)


class CancelExpiredInactiveSplitInvitesTestCase(TestCase):
    @patch('amuse.tasks.zendesk_create_or_update_user')
    def setUp(self, _):
        self.user1 = UserFactory()

        self.release = ReleaseFactory(
            user=self.user1,
            release_date=date(2020, 2, 1),
            status=Release.STATUS_DELIVERED,
        )
        self.song1 = SongFactory(release=self.release)

    @patch('releases.management.commands.cancel_expired_inactive_splits.logger.info')
    def test_does_not_do_anything_for_nonexpired_invites(self, _):
        items = [
            new_split(self.user1, self.song1, 1, ACTIVE, '0.5', is_owner=True),
            new_split(
                inviter=self.user1,
                song=self.song1,
                revision=2,
                status=CONFIRMED,
                rate='0.7',
                is_owner=True,
                expired=False,
            ),
            new_split(self.user1, self.song1, 2, PENDING, '0.3', expired=False),
        ]

        call_command(COMMAND)

        splits = RoyaltySplit.objects.all().order_by('id')
        invites = RoyaltyInvitation.objects.all().order_by('id')

        self.assertEqual(3, splits.count(), "Expected 3 splits")
        self.assertEqual(1, invites.count(), "Expected 1 invite")

        self.assertEqual(items[0].split, splits[0])
        self.assertEqual(items[1].split, splits[1])
        self.assertEqual(items[2].split, splits[2])
        self.assertEqual(items[2].invite, invites[0])

    @patch('releases.management.commands.cancel_expired_inactive_splits.logger.info')
    def test_does_not_do_anything_for_active_invites(self, _):
        items = [
            new_split(self.user1, self.song1, 1, ACTIVE, '1.0', is_owner=True),
            new_split(self.user1, self.song1, 2, ACTIVE, '0.2', is_owner=True),
            new_split(self.user1, self.song1, 2, ACTIVE, '0.8'),
        ]

        call_command(COMMAND)

        splits = RoyaltySplit.objects.all().order_by('id')
        invites = RoyaltyInvitation.objects.all().order_by('id')

        self.assertEqual(3, splits.count())
        self.assertEqual(1, invites.count())

        self.assertEqual(items[0].split, splits[0])
        self.assertEqual(items[1].split, splits[1])
        self.assertEqual(items[2].split, splits[2])

        self.assertEqual(items[2].invite, invites[0])
        self.assertEqual(items[2].invite.status, RoyaltyInvitation.STATUS_ACCEPTED)

    @patch('releases.management.commands.cancel_expired_inactive_splits.logger.info')
    @patch('amuse.vendor.segment.events.split_invites_expired')
    def test_ignore_revision_1_inactive_split_and_invites(self, mock_invite, _):
        items = [
            new_split(self.user1, self.song1, 1, CONFIRMED, '0.5', is_owner=True),
            new_split(self.user1, self.song1, 1, PENDING, '0.3'),
            new_split(self.user1, self.song1, 1, PENDING, '0.2'),
        ]

        call_command(COMMAND)

        splits = RoyaltySplit.objects.all().order_by('id')
        invites = RoyaltyInvitation.objects.all().order_by('id')

        self.assertEqual(3, splits.count(), "Expect 3 splits")
        self.assertEqual(2, invites.count(), "Expect 2 invites")

        self.assertEqual(items[0].split, splits[0])
        self.assertEqual(items[1].split, splits[1])
        self.assertEqual(items[2].split, splits[2])

        self.assertEqual(items[1].invite, invites[0])
        self.assertEqual(items[2].invite, invites[1])

        self.assertEqual(
            0,
            mock_invite.call_count,
            "Expect 0 event to be triggered (there is no splits to delete)",
        )

    @patch('releases.management.commands.cancel_expired_inactive_splits.logger.info')
    @patch(
        'releases.management.commands.cancel_expired_inactive_splits.new_job_id',
        return_value='123xyz',
    )
    @patch('amuse.vendor.segment.events.split_invites_expired')
    def test_delete_inactive_split_and_invites(
        self, mock_split_invites_expired, mock_job_id, mock_info
    ):
        items = [
            new_split(self.user1, self.song1, 1, ACTIVE, '1.0', is_owner=True),
            new_split(self.user1, self.song1, 2, CONFIRMED, '0.5', is_owner=True),
            new_split(self.user1, self.song1, 2, PENDING, '0.3'),
            new_split(self.user1, self.song1, 2, PENDING, '0.2'),
        ]

        call_command(COMMAND)

        splits = RoyaltySplit.objects.all().order_by('id')
        invites = RoyaltyInvitation.objects.all().order_by('id')

        self.assertEqual(1, splits.count(), "Expect 1 split")
        self.assertEqual(0, invites.count(), "Expect 0 invites")

        self.assertEqual(items[0].split, splits[0])

        self.assertEqual(Decimal('1.0'), splits[0].rate)
        self.assertEqual(RoyaltySplit.STATUS_ACTIVE, splits[0].status)
        self.assertEqual(
            1,
            mock_split_invites_expired.call_count,
            "Expect 1 event to be triggered (because there is only one song)",
        )

        archived_splits = [items[1].split, items[2].split, items[3].split]
        calls = [
            call(
                f'Expired inactive splits processed: '
                f'job_id=123xyz, '
                f'inviter_id={self.user1.id}, '
                f'song_id={self.song1.id}, '
                f'revision=2, '
                f'archived_split_ids={[split.id for split in archived_splits]}'
            )
        ]

        for split in archived_splits:
            status = dict(RoyaltySplit.STATUS_CHOICES)[split.status]
            calls.append(
                call(
                    f'Deleted split details: '
                    f'job_id=123xyz, '
                    f'split_id={split.id}, '
                    f'rate={split.rate:.4f}, '
                    f'status={status}, '
                    f'song_id={split.song_id}, '
                    f'user_id={split.user_id}, '
                    f'revision=2, is_owner=False, is_locked=False, '
                    f'created={str(split.created)}, start_date=None, end_date=None.'
                )
            )

        mock_info.assert_has_calls(calls, any_order=True)
        self.assertEqual(mock_info.call_count, 4)


class CancelExpiredInactiveSplitInvitesMultipleSongs(TestCase):
    @patch('amuse.tasks.zendesk_create_or_update_user')
    def setUp(self, _):
        self.user1 = UserFactory()

        self.release1 = ReleaseFactory(
            user=self.user1,
            release_date=timezone.now().today() + timedelta(days=20),
            status=Release.STATUS_DELIVERED,
        )
        self.release2 = ReleaseFactory(
            user=self.user1,
            release_date=timezone.now().today() + timedelta(days=20),
            status=Release.STATUS_RELEASED,
        )

        self.songs = [
            SongFactory(release=self.release1),
            SongFactory(release=self.release1),
            SongFactory(release=self.release2),
        ]

    @patch('releases.management.commands.cancel_expired_inactive_splits.logger.info')
    @patch(
        'releases.management.commands.cancel_expired_inactive_splits.split_invites_expired'
    )
    @patch('amuse.tasks.zendesk_create_or_update_user')
    def test_multiple_revisions_for_multiple_songs(self, _, mock_split_deleted, __):
        items = [
            # song 1 - will delete revision 3
            new_split(self.user1, self.songs[0], 1, ARCHIVED, '1.0', is_owner=True),
            new_split(self.user1, self.songs[0], 2, ACTIVE, '0.8', is_owner=True),
            new_split(self.user1, self.songs[0], 2, ACTIVE, '0.2'),
            new_split(self.user1, self.songs[0], 3, CONFIRMED, '0.8', is_owner=True),
            new_split(self.user1, self.songs[0], 3, PENDING, '0.2'),
            # song 2 - will delete revision 2
            new_split(self.user1, self.songs[1], 1, ACTIVE, '1.0', is_owner=True),
            new_split(self.user1, self.songs[1], 2, PENDING, '0.7'),
            new_split(self.user1, self.songs[1], 2, PENDING, '0.3'),
            # song 3 - will not delete anything
            new_split(self.user1, self.songs[2], 1, CONFIRMED, '0.6', is_owner=True),
            new_split(self.user1, self.songs[2], 1, PENDING, '0.4'),
        ]

        call_command(COMMAND)

        splits = RoyaltySplit.objects.all().order_by('id')
        invites = RoyaltyInvitation.objects.all().order_by('id')

        self.assertEqual(6, splits.count(), "Expect 6 splits")
        self.assertEqual(2, invites.count(), "Expect 2 invites")

        # test splits
        self.assertEqual(items[0].split.id, splits[0].id)
        self.assertEqual(items[1].split.id, splits[1].id)
        self.assertEqual(items[2].split.id, splits[2].id)
        self.assertEqual(items[5].split.id, splits[3].id)
        self.assertEqual(items[8].split.id, splits[4].id)
        self.assertEqual(items[9].split.id, splits[5].id)

        # test invites
        self.assertEqual(items[2].invite.id, invites[0].id)
        self.assertEqual(items[9].invite.id, invites[1].id)

        self.assertEqual(
            2,
            mock_split_deleted.call_count,
            "Expect 2 events to be triggered (there are 2 processed songs)",
        )


class CancelExpiredInactiveSplitInvitesNonLiveSongsTestCase(TestCase):
    @patch('amuse.tasks.zendesk_create_or_update_user')
    def setUp(self, _):
        self.user1 = UserFactory()

        self.release = ReleaseFactory(
            user=self.user1,
            release_date=timezone.now().today() + timedelta(days=20),
            status=Release.STATUS_APPROVED,
        )
        self.song1 = SongFactory(release=self.release)

    @patch('releases.management.commands.cancel_expired_inactive_splits.logger.info')
    def test_does_not_do_anything_for_non_live_tracks_invites(self, _):
        result = new_split(self.user1, self.song1, 1, PENDING, '0.3')

        call_command(COMMAND)

        splits = RoyaltySplit.objects.all().order_by('id')
        invites = RoyaltyInvitation.objects.all().order_by('id')

        self.assertEqual(1, splits.count(), "Expected 1 split")
        self.assertEqual(1, invites.count(), "Expected 1 invite")

        self.assertEqual(result.split, splits[0])
        self.assertEqual(result.invite, invites[0])


class CancelExpiredInactiveSplitForSpecificReleasesTestCase(TestCase):
    @patch('amuse.tasks.zendesk_create_or_update_user')
    def setUp(self, _):
        self.user1 = UserFactory()

        self.release1 = ReleaseFactory(
            user=self.user1,
            release_date=timezone.now().today() + timedelta(days=20),
            status=Release.STATUS_DELIVERED,
        )
        self.release2 = ReleaseFactory(
            user=self.user1,
            release_date=timezone.now().today() + timedelta(days=20),
            status=Release.STATUS_RELEASED,
        )

        self.release3 = ReleaseFactory(
            user=self.user1,
            release_date=timezone.now().today() + timedelta(days=20),
            status=Release.STATUS_RELEASED,
        )

        self.songs = [
            SongFactory(release=self.release1),
            SongFactory(release=self.release1),
            SongFactory(release=self.release2),
            SongFactory(release=self.release3),
        ]

    @patch('releases.management.commands.cancel_expired_inactive_splits.logger.info')
    @patch(
        'releases.management.commands.cancel_expired_inactive_splits.split_invites_expired'
    )
    @patch('amuse.tasks.zendesk_create_or_update_user')
    def test_command_for_specific_releases(self, _, __, ___):
        items = [
            # song 1 - will delete revision 2
            new_split(self.user1, self.songs[0], 1, ACTIVE, '1.0', is_owner=True),
            new_split(self.user1, self.songs[0], 2, CONFIRMED, '0.8', is_owner=True),
            new_split(self.user1, self.songs[0], 2, PENDING, '0.2'),
            # song 2 - will delete revision 2
            new_split(self.user1, self.songs[1], 1, ACTIVE, '1.0', is_owner=True),
            new_split(self.user1, self.songs[1], 2, PENDING, '0.7'),
            new_split(self.user1, self.songs[1], 2, PENDING, '0.3'),
            # song 3 - will not delete anything (release not included in command)
            new_split(self.user1, self.songs[2], 1, ACTIVE, '1.0', is_owner=True),
            new_split(self.user1, self.songs[2], 2, PENDING, '0.5'),
            new_split(self.user1, self.songs[2], 2, PENDING, '0.3'),
            new_split(self.user1, self.songs[2], 2, PENDING, '0.2'),
            # song 4 - will delete revision 2
            new_split(self.user1, self.songs[3], 1, ACTIVE, '1.0', is_owner=True),
            new_split(self.user1, self.songs[3], 2, PENDING, '0.6'),
            new_split(self.user1, self.songs[3], 2, PENDING, '0.4'),
        ]

        call_command(COMMAND, '-r', self.release1.id, self.release3.id)

        splits = RoyaltySplit.objects.all().order_by('id')
        invites = RoyaltyInvitation.objects.all().order_by('id')

        self.assertEqual(7, splits.count(), "Expect 7 splits")
        self.assertEqual(3, invites.count(), "Expect 3 invites")

        # test splits
        self.assertEqual(items[0].split.id, splits[0].id)
        self.assertEqual(items[3].split.id, splits[1].id)
        self.assertEqual(items[6].split.id, splits[2].id)
        self.assertEqual(items[7].split.id, splits[3].id)
        self.assertEqual(items[8].split.id, splits[4].id)
        self.assertEqual(items[9].split.id, splits[5].id)
        self.assertEqual(items[10].split.id, splits[6].id)

        # test invites
        self.assertEqual(items[7].invite.id, invites[0].id)
        self.assertEqual(items[8].invite.id, invites[1].id)
        self.assertEqual(items[9].invite.id, invites[2].id)
