from datetime import date
from decimal import Decimal

import pytest
import responses
from freezegun import freeze_time

from django.core.management import call_command
from django.test import TestCase, override_settings

from amuse.tests.helpers import (
    add_zendesk_mock_post_response,
    ZENDESK_MOCK_API_URL_TOKEN,
)

from releases.management.commands.cancel_pending_splits import (
    BOTH_DATES_ERROR_MSG,
    END_DATE_ERROR_MSG,
)
from releases.models import Release, RoyaltySplit
from releases.tests.factories import (
    SongFactory,
    RoyaltySplitFactory,
    ReleaseFactory,
    ReleaseArtistRoleFactory,
)
from users.tests.factories import UserFactory, Artistv2Factory


STATUS_ACTIVE = RoyaltySplit.STATUS_ACTIVE
STATUS_PENDING = RoyaltySplit.STATUS_PENDING
STATUS_ARCHIVED = RoyaltySplit.STATUS_ARCHIVED
STATUS_CONFIRMED = RoyaltySplit.STATUS_CONFIRMED


@override_settings(**ZENDESK_MOCK_API_URL_TOKEN)
class CancelPendingSplitsTestCase(TestCase):
    @pytest.fixture(autouse=True)
    def _pass_fixtures(self, capsys):
        self.capsys = capsys

    @responses.activate
    def setUp(self):
        add_zendesk_mock_post_response()

        self.user1 = UserFactory()
        self.user2 = UserFactory()

        self.release = ReleaseFactory(
            user=self.user1,
            release_date=date(2020, 2, 1),
            status=Release.STATUS_DELIVERED,
        )
        self.song1 = SongFactory(release=self.release)
        artist = Artistv2Factory(owner=self.user1)
        ReleaseArtistRoleFactory(
            artist=artist, release=self.release, main_primary_artist=True
        )

    def test_replaces_first_revision_pending_splits(self):
        with freeze_time('2020-01-01'):
            RoyaltySplitFactory(
                user=self.user1,
                song=self.song1,
                rate=Decimal('0.5'),
                status=STATUS_CONFIRMED,
                start_date=None,
                end_date=None,
                revision=1,
                is_owner=True,
            )
            RoyaltySplitFactory(
                user=None,
                song=self.song1,
                rate=Decimal('0.5'),
                status=STATUS_PENDING,
                start_date=None,
                end_date=None,
                revision=1,
                is_owner=False,
            )

        with freeze_time("2020-02-01"):
            call_command("cancel_pending_splits")

        splits = RoyaltySplit.objects.all()

        assert splits.count() == 1
        assert splits[0].rate == Decimal("1.0")
        assert splits[0].start_date is None
        assert splits[0].end_date is None
        assert splits[0].status == RoyaltySplit.STATUS_ACTIVE
        assert splits[0].revision == 1
        assert splits[0].is_owner is True

    def test_does_not_do_anything_for_first_revision_active_splits(self):
        with freeze_time('2020-01-01'):
            split = RoyaltySplitFactory(
                user=self.user1,
                song=self.song1,
                rate=Decimal('1.0'),
                status=STATUS_ACTIVE,
                start_date=None,
                end_date=None,
                revision=1,
                is_owner=True,
            )

        with freeze_time("2020-02-01"):
            call_command("cancel_pending_splits")

        splits = RoyaltySplit.objects.all()

        assert splits.count() == 1
        assert splits[0] == split

    def test_does_not_do_anything_for_first_revision_locked_splits(self):
        """This should never happen but if a split is locked we don't touch it"""
        with freeze_time('2020-01-01'):
            split = RoyaltySplitFactory(
                user=self.user1,
                song=self.song1,
                rate=Decimal('1.0'),
                status=STATUS_PENDING,
                start_date=None,
                end_date=None,
                revision=1,
                is_owner=True,
                is_locked=True,
            )

        with freeze_time("2020-02-01"):
            call_command("cancel_pending_splits")

        splits = RoyaltySplit.objects.all()

        assert splits.count() == 1
        assert splits[0] == split

    def test_does_not_do_anything_for_second_revision_with_existing_active_splits(self):
        with freeze_time('2020-01-01'):
            split_1 = RoyaltySplitFactory(
                user=self.user1,
                song=self.song1,
                rate=Decimal('1.0'),
                status=STATUS_ACTIVE,
                start_date=None,
                end_date=None,
                revision=1,
                is_owner=True,
            )
        with freeze_time('2020-01-16'):
            split_2 = RoyaltySplitFactory(
                user=self.user1,
                song=self.song1,
                rate=Decimal('0.5'),
                status=STATUS_CONFIRMED,
                start_date=date(2020, 1, 16),
                end_date=None,
                revision=2,
                is_owner=True,
            )
            split_3 = RoyaltySplitFactory(
                user=None,
                song=self.song1,
                rate=Decimal('0.5'),
                status=STATUS_PENDING,
                start_date=date(2020, 1, 16),
                end_date=None,
                revision=2,
                is_owner=False,
            )

        with freeze_time("2020-02-01"):
            call_command("cancel_pending_splits")

        splits = RoyaltySplit.objects.all()

        assert splits.count() == 3

        assert splits[0] == split_1
        assert splits[1] == split_2
        assert splits[2] == split_3

    def test_cleans_up_faulty_pending_revisions(self):
        self.release.status = Release.STATUS_RELEASED
        self.release.save()
        with freeze_time('2020-01-01'):
            RoyaltySplitFactory(
                user=self.user1,
                song=self.song1,
                rate=Decimal('0.5'),
                status=STATUS_CONFIRMED,
                start_date=None,
                end_date=date(2020, 1, 4),
                revision=1,
                is_owner=True,
            )
            RoyaltySplitFactory(
                user=None,
                song=self.song1,
                rate=Decimal('0.5'),
                status=STATUS_PENDING,
                start_date=None,
                end_date=date(2020, 1, 4),
                revision=1,
                is_owner=False,
            )
        with freeze_time('2020-01-05'):
            RoyaltySplitFactory(
                user=self.user1,
                song=self.song1,
                rate=Decimal('0.5'),
                status=STATUS_CONFIRMED,
                start_date=date(2020, 1, 5),
                end_date=None,
                revision=2,
                is_owner=True,
            )
            RoyaltySplitFactory(
                user=None,
                song=self.song1,
                rate=Decimal('0.5'),
                status=STATUS_PENDING,
                start_date=date(2020, 1, 5),
                end_date=None,
                revision=2,
                is_owner=False,
            )

        with freeze_time("2020-02-01"):
            call_command("cancel_pending_splits")

        splits = RoyaltySplit.objects.all()

        assert splits.count() == 1
        assert splits[0].rate == Decimal("1.0")
        assert splits[0].start_date is None
        assert splits[0].end_date is None
        assert splits[0].status == RoyaltySplit.STATUS_ACTIVE
        assert splits[0].revision == 1
        assert splits[0].is_owner is True

    def test_allocates_owner_split_rate_correctly(self):
        self.release.status = Release.STATUS_TAKEDOWN
        self.release.save()
        with freeze_time('2020-01-01'):
            RoyaltySplitFactory(
                user=self.user1,
                song=self.song1,
                rate=Decimal('0.5'),
                status=STATUS_CONFIRMED,
                start_date=None,
                end_date=None,
                revision=1,
                is_owner=True,
            )
            RoyaltySplitFactory(
                user=self.user2,
                song=self.song1,
                rate=Decimal('0.25'),
                status=STATUS_CONFIRMED,
                start_date=None,
                end_date=None,
                revision=1,
                is_owner=False,
            )
            RoyaltySplitFactory(
                user=None,
                song=self.song1,
                rate=Decimal('0.05'),
                status=STATUS_PENDING,
                start_date=None,
                end_date=None,
                revision=1,
                is_owner=False,
            )
            RoyaltySplitFactory(
                user=None,
                song=self.song1,
                rate=Decimal('0.1'),
                status=STATUS_PENDING,
                start_date=None,
                end_date=None,
                revision=1,
                is_owner=False,
            )
            RoyaltySplitFactory(
                user=None,
                song=self.song1,
                rate=Decimal('0.1'),
                status=STATUS_PENDING,
                start_date=None,
                end_date=None,
                revision=1,
                is_owner=False,
            )

        with freeze_time("2020-02-01"):
            call_command("cancel_pending_splits")

        splits = RoyaltySplit.objects.all()

        assert splits.count() == 2

        split_1 = splits.get(user=self.user1)
        split_2 = splits.get(user=self.user2)

        assert split_1.rate == Decimal("0.75")
        assert split_2.rate == Decimal("0.25")
        assert split_1.is_owner is True
        assert split_2.is_owner is False

    def test_cleanup_faulty_songs_without_royaltysplits(self):
        with freeze_time("2020-02-01"):
            call_command("cancel_pending_splits")

        splits = RoyaltySplit.objects.all()
        assert splits.count() == 1

        split = splits.get()

        assert split.user == self.song1.release.user
        assert split.rate == Decimal("1.00")
        assert split.start_date is None
        assert split.end_date is None
        assert split.revision == 1
        assert split.status == RoyaltySplit.STATUS_ACTIVE

    def test_date_range_with_pending_splits(self):
        with freeze_time('2020-01-01'):
            RoyaltySplitFactory(
                user=self.user1,
                song=self.song1,
                rate=Decimal('0.5'),
                status=STATUS_CONFIRMED,
                start_date=None,
                end_date=None,
                revision=1,
            )
            RoyaltySplitFactory(
                user=None,
                song=self.song1,
                rate=Decimal('0.5'),
                status=STATUS_PENDING,
                start_date=None,
                end_date=None,
                revision=1,
            )
        with freeze_time("2020-02-01"):
            call_command(
                "cancel_pending_splits",
                "--start-date=2020-01-01",
                "--end-date=2020-01-15",
            )

        assert RoyaltySplit.objects.all().count() == 2

        with freeze_time("2020-02-02"):
            call_command(
                "cancel_pending_splits",
                "--start-date=2020-01-15",
                "--end-date=2020-02-01",
            )

        splits = RoyaltySplit.objects.all()

        assert splits.count() == 1
        assert splits[0].rate == Decimal("1.0")
        assert splits[0].start_date is None
        assert splits[0].end_date is None
        assert splits[0].status == RoyaltySplit.STATUS_ACTIVE
        assert splits[0].revision == 1

    def test_date_range_without_royaltysplits(self):
        with freeze_time("2020-02-01"):
            call_command(
                "cancel_pending_splits",
                "--start-date=2020-01-01",
                "--end-date=2020-01-15",
            )

        assert RoyaltySplit.objects.all().count() == 0

        with freeze_time("2020-02-02"):
            call_command(
                "cancel_pending_splits",
                "--start-date=2020-01-15",
                "--end-date=2020-02-01",
            )

        splits = RoyaltySplit.objects.all()
        assert splits.count() == 1

        split = splits.get()

        assert split.user == self.song1.release.user
        assert split.rate == Decimal("1.00")
        assert split.start_date is None
        assert split.end_date is None
        assert split.revision == 1
        assert split.status == RoyaltySplit.STATUS_ACTIVE

    def test_two_pending_splits_allocates_correctly_back_to_owner(self):
        with freeze_time('2020-01-01'):
            RoyaltySplitFactory(
                user=None,
                song=self.song1,
                rate=Decimal('0.2'),
                status=STATUS_PENDING,
                start_date=None,
                end_date=None,
                revision=1,
                is_owner=False,
            )
            RoyaltySplitFactory(
                user=None,
                song=self.song1,
                rate=Decimal('0.8'),
                status=STATUS_PENDING,
                start_date=None,
                end_date=None,
                revision=1,
                is_owner=False,
            )

        with freeze_time("2020-02-01"):
            call_command("cancel_pending_splits")

        splits = RoyaltySplit.objects.all()

        assert splits.count() == 1

        split = splits.get()

        assert split.user == self.user1
        assert split.rate == Decimal("1.00")
        assert split.start_date is None
        assert split.end_date is None
        assert split.revision == 1
        assert split.status == RoyaltySplit.STATUS_ACTIVE
        assert split.is_owner is True

    def test_confirmed_and_pending_splits_allocates_correctly_back_to_owner(self):
        with freeze_time('2020-01-01'):
            RoyaltySplitFactory(
                user=None,
                song=self.song1,
                rate=Decimal('0.2'),
                status=STATUS_PENDING,
                start_date=None,
                end_date=None,
                revision=1,
                is_owner=False,
            )
            RoyaltySplitFactory(
                user=self.user2,
                song=self.song1,
                rate=Decimal('0.8'),
                status=STATUS_CONFIRMED,
                start_date=None,
                end_date=None,
                revision=1,
                is_owner=False,
            )

        with freeze_time("2020-02-01"):
            call_command("cancel_pending_splits")

        splits = RoyaltySplit.objects.all()

        assert splits.count() == 2

        split_1 = splits.get(user=self.user1)
        split_2 = splits.get(user=self.user2)

        assert split_1.rate == Decimal("0.2")
        assert split_1.start_date is None
        assert split_1.end_date is None
        assert split_1.revision == 1
        assert split_1.status == RoyaltySplit.STATUS_ACTIVE
        assert split_1.is_owner is True

        assert split_2.rate == Decimal("0.8")
        assert split_2.start_date is None
        assert split_2.end_date is None
        assert split_2.revision == 1
        assert split_2.status == RoyaltySplit.STATUS_ACTIVE
        assert split_2.is_owner is False

    def test_mixed_splits_allocates_correctly_back_to_owner(self):
        with freeze_time('2020-01-01'):
            RoyaltySplitFactory(
                user=self.user1,
                song=self.song1,
                rate=Decimal('0.2'),
                status=STATUS_CONFIRMED,
                start_date=None,
                end_date=None,
                revision=1,
                is_owner=True,
            )
            RoyaltySplitFactory(
                user=None,
                song=self.song1,
                rate=Decimal('0.2'),
                status=STATUS_PENDING,
                start_date=None,
                end_date=None,
                revision=1,
                is_owner=False,
            )
            RoyaltySplitFactory(
                user=self.user2,
                song=self.song1,
                rate=Decimal('0.6'),
                status=STATUS_CONFIRMED,
                start_date=None,
                end_date=None,
                revision=1,
                is_owner=False,
            )

        with freeze_time("2020-02-01"):
            call_command("cancel_pending_splits")

        splits = RoyaltySplit.objects.all()

        assert splits.count() == 2

        split_1 = splits.get(user=self.user1)
        split_2 = splits.get(user=self.user2)

        assert split_1.rate == Decimal("0.4")
        assert split_1.start_date is None
        assert split_1.end_date is None
        assert split_1.revision == 1
        assert split_1.status == RoyaltySplit.STATUS_ACTIVE
        assert split_1.is_owner is True

        assert split_2.rate == Decimal("0.6")
        assert split_2.start_date is None
        assert split_2.end_date is None
        assert split_2.revision == 1
        assert split_2.status == RoyaltySplit.STATUS_ACTIVE
        assert split_2.is_owner is False

    def test_must_specify_both_dates_or_nonw(self):
        with freeze_time("2020-02-01"):
            call_command("cancel_pending_splits", "--start-date=2020-01-01")

        captured = self.capsys.readouterr()
        assert captured.out == "%s\n" % BOTH_DATES_ERROR_MSG

    def test_cannot_cancel_splits_for_non_released_releases(self):
        with freeze_time("2020-02-01"):
            call_command(
                "cancel_pending_splits",
                "--start-date=2020-01-01",
                "--end-date=2020-02-15",
            )

        captured = self.capsys.readouterr()
        assert captured.out == "%s\n" % END_DATE_ERROR_MSG
