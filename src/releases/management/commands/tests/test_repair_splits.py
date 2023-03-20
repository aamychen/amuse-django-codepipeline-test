from decimal import Decimal
from unittest import mock

from django.core.management import call_command

from amuse.tests.test_api.base import AmuseAPITestCase
from releases.models import RoyaltySplit
from releases.tests.factories import (
    SongFactory,
    RoyaltySplitFactory,
    ReleaseFactory,
    ReleaseArtistRoleFactory,
)
from users.tests.factories import Artistv2Factory, UserFactory, RoyaltyInvitationFactory


class RepairSplitsTestCase(AmuseAPITestCase):
    @mock.patch('amuse.tasks.zendesk_create_or_update_user')
    def setUp(self, mock_zendesk):
        self.user = UserFactory()
        self.release = ReleaseFactory(user=self.user)
        self.song = SongFactory(release=self.release)
        artist = Artistv2Factory(owner=self.user)
        ReleaseArtistRoleFactory(
            artist=artist, release=self.release, main_primary_artist=True
        )
        self.user2 = UserFactory()
        self.user3 = UserFactory()
        self.user4 = UserFactory()

        self.split_1 = RoyaltySplitFactory(
            user=self.user, song=self.song, rate=Decimal("0.6"), revision=1
        )
        self.split_2 = RoyaltySplitFactory(
            user=self.user2, song=self.song, rate=Decimal("0.4"), revision=1
        )

    def test_repair_skips_locked_splits(self):
        """This should never happen but if a split is locked we don't touch it"""
        self.split_2.is_owner = True
        self.split_2.is_locked = True
        self.split_2.save()

        call_command("repair_splits", "--fix-type=invalid_owner")

        self.split_1.refresh_from_db()
        self.split_2.refresh_from_db()

        assert self.split_1.is_owner is True
        assert self.split_2.is_owner is True

        self.split_1.user = self.user
        self.split_1.save()

        call_command("repair_splits", "--fix-type=same_user")

        self.split_1.refresh_from_db()
        self.split_2.refresh_from_db()

        splits = RoyaltySplit.objects.all()

        assert splits.count() == 2
        assert splits.get(pk=self.split_1.pk) == self.split_1
        assert splits.get(pk=self.split_2.pk) == self.split_2

    def test_repair_invalid_true_owner(self):
        self.split_2.is_owner = True
        self.split_2.save()

        call_command("repair_splits", "--fix-type=invalid_owner")

        self.split_1.refresh_from_db()
        self.split_2.refresh_from_db()

        assert self.split_1.is_owner is True
        assert self.split_2.is_owner is False

    def test_repair_invalid_true_owner_with_existing_release(self):
        self.split_2.is_owner = True
        self.split_2.save()

        call_command(
            "repair_splits",
            "--fix-type=invalid_owner",
            "--release-ids=%s" % self.release.id,
        )

        self.split_1.refresh_from_db()
        self.split_2.refresh_from_db()

        assert self.split_1.is_owner is True
        assert self.split_2.is_owner is False

    def test_repair_invalid_true_owner_with_non_existing_release(self):
        self.split_2.is_owner = True
        self.split_2.save()

        call_command(
            "repair_splits",
            "--fix-type=invalid_owner",
            "--release-ids=%s" % str(self.release.id + 10),
        )

        self.split_1.refresh_from_db()
        self.split_2.refresh_from_db()

        assert self.split_1.is_owner is True

        # No change as this release was not included in run
        assert self.split_2.is_owner is True

    def test_repair_invalid_false_owner(self):
        self.split_1.is_owner = False
        self.split_1.save()

        call_command("repair_splits", "--fix-type=invalid_owner")

        self.split_1.refresh_from_db()
        self.split_2.refresh_from_db()

        assert self.split_1.is_owner is True
        assert self.split_2.is_owner is False

    def test_repair_same_user_with_owner_true(self):
        self.split_2.user = self.user
        self.split_2.save()

        call_command("repair_splits", "--fix-type=same_user")

        splits = RoyaltySplit.objects.all()

        assert splits.count() == 1
        assert splits[0].user == self.user
        assert splits[0].rate == Decimal("1.0")
        assert splits[0].is_owner is True

    def test_repair_same_user_with_owner_false(self):
        self.split_1.user = self.user2
        self.split_1.is_owner = False
        self.split_1.save()

        call_command("repair_splits", "--fix-type=same_user")

        splits = RoyaltySplit.objects.all()

        assert splits.count() == 1
        assert splits[0].user == self.user2
        assert splits[0].rate == Decimal("1.0")
        assert splits[0].is_owner is False

    @mock.patch('amuse.tasks.zendesk_create_or_update_user')
    def test_repair_same_user_rate(self, mock_zendesk):
        RoyaltySplitFactory(user=None, song=self.song, rate=Decimal("0.10"), revision=1)
        RoyaltySplitFactory(user=None, song=self.song, rate=Decimal("0.05"), revision=1)
        self.split_2.rate = Decimal("0.25")
        self.split_2.user = self.user
        self.split_2.save()

        call_command("repair_splits", "--fix-type=same_user")

        splits = RoyaltySplit.objects.all()

        assert splits.count() == 3

        changed_split = splits.get(user_id=self.user.id)
        other_splits = splits.filter(user_id__isnull=True)

        assert changed_split.rate == Decimal("0.85")
        assert changed_split.is_owner is True
        assert other_splits[0].rate + other_splits[1].rate == Decimal("0.15")

    @mock.patch('amuse.tasks.zendesk_create_or_update_user')
    def test_repair_same_user_with_multiple_songs(self, mock_zendesk):
        RoyaltySplitFactory(user=self.user3)
        RoyaltySplitFactory(user=self.user4)
        self.split_2.user = self.user
        self.split_2.save()

        call_command("repair_splits", "--fix-type=same_user")

        splits = RoyaltySplit.objects.filter(song=self.song)

        assert splits.count() == 1
        assert splits[0].user == self.user
        assert splits[0].rate == Decimal("1.0")
        assert splits[0].is_owner is True

    @mock.patch('amuse.tasks.zendesk_create_or_update_user')
    def test_repair_same_user_multiple_splits(self, mock_zendesk):
        self.split_1.rate = Decimal("0.25")
        self.split_1.save()
        RoyaltySplitFactory(
            user=self.user,
            song=self.song,
            rate=Decimal("0.15"),
            revision=1,
            is_owner=False,
        )
        RoyaltySplitFactory(
            user=self.user,
            song=self.song,
            rate=Decimal("0.2"),
            revision=1,
            is_owner=True,
        )

        call_command("repair_splits", "--fix-type=same_user")

        splits = RoyaltySplit.objects.all()
        changed_split = splits.get(user_id=self.user.id)
        other_split = splits.get(user_id=self.user2)

        assert splits.count() == 2
        assert changed_split.rate == Decimal("0.6")
        assert changed_split.is_owner is True
        assert other_split.rate == Decimal("0.4")
        assert other_split.is_owner is False

    @mock.patch('amuse.tasks.zendesk_create_or_update_user')
    def test_repair_same_user_multiple_splits_specific_release_id(self, mock_zendesk):
        self.split_1.rate = Decimal("0.25")
        self.split_1.save()
        RoyaltySplitFactory(
            user=self.user,
            song=self.song,
            rate=Decimal("0.15"),
            revision=1,
            is_owner=False,
        )
        RoyaltySplitFactory(
            user=self.user,
            song=self.song,
            rate=Decimal("0.2"),
            revision=1,
            is_owner=True,
        )

        call_command(
            "repair_splits",
            "--fix-type=same_user",
            "--release-ids=%s" % self.release.id,
        )

        splits = RoyaltySplit.objects.all()
        changed_split = splits.get(user_id=self.user.id)
        other_split = splits.get(user_id=self.user2)

        assert splits.count() == 2
        assert changed_split.rate == Decimal("0.6")
        assert changed_split.is_owner is True
        assert other_split.rate == Decimal("0.4")
        assert other_split.is_owner is False
