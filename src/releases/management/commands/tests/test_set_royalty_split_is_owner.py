import responses
from datetime import date
from decimal import Decimal
from freezegun import freeze_time

from django.core.management import call_command
from django.test import TestCase, override_settings

from amuse.tests.helpers import (
    add_zendesk_mock_post_response,
    ZENDESK_MOCK_API_URL_TOKEN,
)

from releases.models import Release, RoyaltySplit
from releases.tests.factories import (
    SongFactory,
    RoyaltySplitFactory,
    ReleaseFactory,
    ReleaseArtistRoleFactory,
)

from users.tests.factories import UserFactory, Artistv2Factory


@override_settings(**ZENDESK_MOCK_API_URL_TOKEN)
class SetRoyaltySplitIsOwnerTestCase(TestCase):
    @responses.activate
    def setUp(self):
        add_zendesk_mock_post_response()

        self.user1 = UserFactory()
        self.user2 = UserFactory()

        release = ReleaseFactory(
            user=self.user1,
            release_date=date(2020, 2, 1),
            status=Release.STATUS_APPROVED,
        )
        self.song1 = SongFactory(release=release)

        self.release2 = ReleaseFactory(
            user=self.user2,
            release_date=date(2020, 2, 1),
            status=Release.STATUS_APPROVED,
        )
        self.song2 = SongFactory(release=self.release2)

        artist = Artistv2Factory(owner=self.user1)
        ReleaseArtistRoleFactory(
            artist=artist, release=release, main_primary_artist=True
        )
        artist2 = Artistv2Factory(owner=self.user2)
        ReleaseArtistRoleFactory(
            artist=artist2, release=self.release2, main_primary_artist=True
        )

        # This split is not used in the test but used when debugging the script
        # to confirm that is_owner=True splits are filtered out
        self.split1 = RoyaltySplitFactory(
            user=self.user1,
            song=self.song1,
            rate=Decimal('1.0'),
            status=RoyaltySplit.STATUS_ARCHIVED,
            start_date=None,
            end_date=date(2020, 2, 10),
            revision=1,
        )
        self.split2 = RoyaltySplitFactory(
            user=self.user1,
            song=self.song1,
            rate=Decimal('0.5'),
            status=RoyaltySplit.STATUS_ACTIVE,
            start_date=date(2020, 2, 11),
            end_date=None,
            revision=2,
        )
        self.split3 = RoyaltySplitFactory(
            user=self.user2,
            song=self.song1,
            rate=Decimal('0.5'),
            status=RoyaltySplit.STATUS_ACTIVE,
            start_date=date(2020, 2, 11),
            end_date=None,
            revision=2,
        )
        self.split4 = RoyaltySplitFactory(
            user=self.user2,
            song=self.song2,
            rate=Decimal('1.0'),
            status=RoyaltySplit.STATUS_ACTIVE,
            start_date=date(2020, 2, 11),
            end_date=None,
            revision=1,
        )

        # Force is_owner status to rule out any bugs in save() so we can simulate
        # pre-existing splits
        self.split1.is_owner = True
        self.split1.save()
        self.split1.refresh_from_db()
        self.split2.is_owner = False
        self.split2.save()
        self.split2.refresh_from_db()
        self.split3.is_owner = False
        self.split3.save()
        self.split3.refresh_from_db()
        self.split4.is_owner = False
        self.split4.save()
        self.split4.refresh_from_db()

    def test_sets_split_owner_correctly(self):
        call_command("set_royalty_split_is_owner")

        self.split2.refresh_from_db()
        self.split3.refresh_from_db()

        assert self.split2.is_owner
        assert not self.split3.is_owner

    def test_filter_by_release_id_works_correctly(self):
        call_command(
            "set_royalty_split_is_owner", "--release_ids=%s" % self.release2.pk
        )

        self.split1.refresh_from_db()
        self.split2.refresh_from_db()
        self.split3.refresh_from_db()
        self.split4.refresh_from_db()

        assert self.split1.is_owner
        assert not self.split2.is_owner
        assert not self.split3.is_owner
        assert self.split4.is_owner
