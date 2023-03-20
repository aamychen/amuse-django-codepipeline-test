from datetime import date, timedelta
from decimal import Decimal
from unittest import mock

from freezegun import freeze_time
from django.contrib.admin.models import LogEntry, CHANGE
from django.contrib.contenttypes.models import ContentType
from django.core.management import call_command
from django.test import TestCase, override_settings

from releases.models import Release, RoyaltySplit
from releases.tests.factories import (
    SongFactory,
    RoyaltySplitFactory,
    ReleaseFactory,
    ReleaseArtistRoleFactory,
)

from users.tests.factories import UserFactory, Artistv2Factory


class FixChangedArtistOwnerSplitsTestCase(TestCase):
    @mock.patch("amuse.tasks.zendesk_create_or_update_user")
    def setUp(self, mock_zendesk):
        self.user1 = UserFactory()
        self.user2 = UserFactory()
        self.user3 = UserFactory()
        self.user4 = UserFactory()
        self.user5 = UserFactory()

        self.release1 = release = ReleaseFactory(
            user=self.user1, status=Release.STATUS_APPROVED
        )
        self.song1 = SongFactory(release=self.release1)

        self.artist = Artistv2Factory(owner=self.user1)
        ReleaseArtistRoleFactory(
            artist=self.artist, release=self.release1, main_primary_artist=True
        )

        self.release2 = ReleaseFactory(user=self.user3, status=Release.STATUS_APPROVED)
        self.song2 = SongFactory(release=self.release2)

        with freeze_time("2020-3-2"):
            self.artist2 = Artistv2Factory(owner=self.user3)
        ReleaseArtistRoleFactory(
            artist=self.artist2, release=self.release2, main_primary_artist=True
        )

        self.split1 = RoyaltySplitFactory(
            user=self.user1,
            song=self.song1,
            rate=Decimal('1.0'),
            status=RoyaltySplit.STATUS_ACTIVE,
            start_date=None,
            end_date=None,
            revision=1,
        )
        self.split1.is_owner = False
        self.split1.save()
        self.split1.refresh_from_db()

        self.split2 = RoyaltySplitFactory(
            user=self.user3,
            song=self.song2,
            rate=Decimal('0.3'),
            status=RoyaltySplit.STATUS_ARCHIVED,
            start_date=None,
            end_date=date(2020, 3, 31),
            revision=1,
        )
        self.split3 = RoyaltySplitFactory(
            user=self.user4,
            song=self.song2,
            rate=Decimal('0.7'),
            status=RoyaltySplit.STATUS_ARCHIVED,
            start_date=None,
            end_date=date(2020, 3, 31),
            revision=1,
        )
        self.split4 = RoyaltySplitFactory(
            user=self.user4,
            song=self.song2,
            rate=Decimal('0.5'),
            status=RoyaltySplit.STATUS_ACTIVE,
            start_date=date(2020, 4, 1),
            end_date=None,
            revision=2,
        )
        self.split5 = RoyaltySplitFactory(
            user=self.user3,
            song=self.song2,
            rate=Decimal('0.5'),
            status=RoyaltySplit.STATUS_ACTIVE,
            start_date=date(2020, 4, 1),
            end_date=None,
            revision=2,
        )
        self.split2.is_owner = False
        self.split3.is_owner = False
        self.split4.is_owner = False
        self.split5.is_owner = False
        self.split2.save()
        self.split3.save()
        self.split4.save()
        self.split5.save()
        self.split2.refresh_from_db()
        self.split3.refresh_from_db()
        self.split4.refresh_from_db()
        self.split5.refresh_from_db()

    def test_changed_artist_owner_split_is_fixed(self):
        # Artist owner is changed manually
        self.artist.owner = self.user2
        self.artist.save()
        self.artist.refresh_from_db()

        # Create LogEntry manually as post_save signal is not triggered from this test
        LogEntry.objects.create(
            content_type_id=ContentType.objects.get(model="artistv2").id,
            user_id=self.user1.id,
            object_id=self.artist.id,
            action_flag=CHANGE,
        )

        # Split owner is still self.user1 and is_owner=False as the
        # set_royalty_split_is_owner script does not catch this as
        # split.user != artist.owner
        assert self.split1.user == self.user1
        assert self.split1.is_owner is False

        call_command("fix_splits_with_changed_artist_owners")

        self.split1.refresh_from_db()

        # The previous split has been archived and is_owner and end_date are set
        assert self.split1.user == self.user1
        assert self.split1.is_owner is True
        assert self.split1.end_date == date.today() - timedelta(days=1)
        assert self.split1.revision == 1
        assert self.split1.status == RoyaltySplit.STATUS_ARCHIVED

        new_split = RoyaltySplit.objects.get(user_id=self.user2.id)

        # A new active split for the new artist owner has been created
        assert new_split.user == self.user2
        assert new_split.is_owner is True
        assert new_split.start_date == date.today()
        assert new_split.revision == 2
        assert new_split.status == RoyaltySplit.STATUS_ACTIVE

    def test_skip_archived_and_fix_active_splits(self):
        initial_splits = RoyaltySplit.objects.all().order_by("pk").values()

        assert initial_splits.count() == 5

        # Owner change from self.user3 to self.user4
        with freeze_time("2020-4-20"):
            self.artist2.owner = self.user4
            self.artist2.save()
            self.artist2.refresh_from_db()

        LogEntry.objects.create(
            content_type_id=ContentType.objects.get(model="artistv2").id,
            user_id=self.user5.id,
            object_id=self.artist2.id,
            action_flag=CHANGE,
        )

        call_command("fix_splits_with_changed_artist_owners")

        self.split2.refresh_from_db()
        self.split3.refresh_from_db()
        self.split4.refresh_from_db()
        self.split5.refresh_from_db()

        first_run_splits = RoyaltySplit.objects.all().order_by("pk").values()
        assert first_run_splits.count() == 7

        assert self.split4.status == RoyaltySplit.STATUS_ARCHIVED
        assert self.split5.status == RoyaltySplit.STATUS_ARCHIVED
        assert self.split4.end_date == date(2020, 4, 19)
        assert self.split5.end_date == date(2020, 4, 19)

    def test_skip_archived_splits_and_skip_multiple_owner_changes(self):
        self.split4.is_owner = True
        self.split4.save()

        initial_splits = RoyaltySplit.objects.all().order_by("pk").values()

        self.artist2.owner = self.user4
        self.artist2.save()
        self.artist2.refresh_from_db()

        LogEntry.objects.create(
            content_type_id=ContentType.objects.get(model="artistv2").id,
            user_id=self.user4.id,
            object_id=self.artist2.id,
            action_flag=CHANGE,
            action_time=date(2020, 3, 1),
        )

        call_command("fix_splits_with_changed_artist_owners")
        first_run_splits = RoyaltySplit.objects.all().order_by("pk").values()

        # No change as previous artist owner is on an archived split that we don't
        # process and self.split4.owner is the current owner
        assert list(initial_splits) == list(first_run_splits)

        # Now the artist owner changes again to another user
        self.artist2.owner = self.user5
        self.artist2.save()
        self.artist2.refresh_from_db()

        LogEntry.objects.create(
            content_type_id=ContentType.objects.get(model="artistv2").id,
            user_id=self.user5.id,
            object_id=self.artist2.id,
            action_flag=CHANGE,
            action_time=date(2020, 4, 10),
        )

        call_command("fix_splits_with_changed_artist_owners")
        second_run_splits = RoyaltySplit.objects.all().order_by("pk").values()

        # No change as this artist have multiple owner changes and we skip those
        assert list(initial_splits) == list(second_run_splits)

    def test_process_releases(self):
        self.artist.owner = self.user2
        self.artist.save()
        self.artist.refresh_from_db()

        LogEntry.objects.create(
            content_type_id=ContentType.objects.get(model="artistv2").id,
            user_id=self.user1.id,
            object_id=self.artist.id,
            action_flag=CHANGE,
            change_message='[{"changed": {"fields": ["owner"]}}',
        )

        call_command(
            "fix_splits_with_changed_artist_owners",
            "--fix-releases=%s" % self.release1.id,
        )

        # The previous split has been archived and is_owner and end_date are set
        self.split1.refresh_from_db()
        assert self.split1.user == self.user1
        assert self.split1.is_owner is True
        assert self.split1.end_date == date.today() - timedelta(days=1)
        assert self.split1.revision == 1
        assert self.split1.status == RoyaltySplit.STATUS_ARCHIVED

        new_split = RoyaltySplit.objects.get(user_id=self.user2.id)

        # A new active split for the new artist owner has been created
        assert new_split.user == self.user2
        assert new_split.is_owner is True
        assert new_split.start_date == date.today()
        assert new_split.revision == 2
        assert new_split.status == RoyaltySplit.STATUS_ACTIVE
