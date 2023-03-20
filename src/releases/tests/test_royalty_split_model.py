import pytest
from datetime import date
from freezegun import freeze_time

from django.test import TestCase, override_settings
from django.utils import timezone
import responses

from amuse.tests.helpers import (
    add_zendesk_mock_post_response,
    ZENDESK_MOCK_API_URL_TOKEN,
)
from releases.managers import RoyaltySplitDifferentRevisionsError
from releases.models import RoyaltySplit
from releases.tests.factories import (
    SongFactory,
    RoyaltySplitFactory,
    ReleaseFactory,
    ReleaseArtistRoleFactory,
)
from users.tests.factories import Artistv2Factory, UserFactory, RoyaltyInvitationFactory


@override_settings(**ZENDESK_MOCK_API_URL_TOKEN)
class RoyaltySplitTestCase(TestCase):
    @responses.activate
    def setUp(self):
        add_zendesk_mock_post_response()

        # Random roles required to make sure invalid_true_owner and invalid_false_owner
        # OuterRef works as expected as they return the first owner_id from the subquery.
        ReleaseArtistRoleFactory(main_primary_artist=False)
        ReleaseArtistRoleFactory(main_primary_artist=True)

        self.user = UserFactory()
        release = ReleaseFactory(user=self.user)
        self.song = SongFactory(release=release)
        artist = Artistv2Factory(owner=self.user)
        ReleaseArtistRoleFactory(
            artist=artist, release=release, main_primary_artist=True
        )
        self.user2 = UserFactory()

    @responses.activate
    def test_get_user_name_returns_user_name(self):
        add_zendesk_mock_post_response()

        royalty_split = RoyaltySplitFactory(
            user=self.user, song=self.song, start_date=timezone.now().today(), rate=1.0
        )

        self.assertEqual(royalty_split.get_user_name(), self.user.name)

    @responses.activate
    def test_get_user_name_returns_royalty_invitation_name(self):
        add_zendesk_mock_post_response()

        royalty_split = RoyaltySplitFactory(
            user=None, song=self.song, start_date=timezone.now().today(), rate=1.0
        )
        royalty_invitation = RoyaltyInvitationFactory(royalty_split=royalty_split)

        self.assertEqual(royalty_split.get_user_name(), royalty_invitation.name)

    @responses.activate
    def test_get_user_profile_photo_url_returns_none_when_royalty_split_doesnt_have_user(
        self,
    ):
        add_zendesk_mock_post_response()

        royalty_split = RoyaltySplitFactory(
            user=None, song=self.song, start_date=timezone.now().today(), rate=1.0
        )

        self.assertIsNone(royalty_split.get_user_profile_photo_url())

    @responses.activate
    def test_get_user_profile_photo_url_returns_user_profile_photo_when_royalty_split_have_user(
        self,
    ):
        add_zendesk_mock_post_response()

        royalty_split = RoyaltySplitFactory(
            user=self.user, song=self.song, start_date=timezone.now().today(), rate=1.0
        )

        self.assertEqual(
            royalty_split.get_user_profile_photo_url(), self.user.profile_photo
        )

    def test_activate_splits(self):
        with freeze_time("2020-01-01"):
            split_1 = RoyaltySplitFactory(
                user=self.user,
                song=self.song,
                start_date=timezone.now().today(),
                rate=1.0,
                status=RoyaltySplit.STATUS_ACTIVE,
                revision=1,
            )
        with freeze_time("2020-02-01"):
            split_2 = RoyaltySplitFactory(
                user=self.user,
                song=self.song,
                start_date=timezone.now().today(),
                rate=1.0,
                status=RoyaltySplit.STATUS_PENDING,
                revision=2,
            )

            RoyaltySplit.objects.filter(revision=1).archive()
            RoyaltySplit.objects.filter(revision=2).activate()

        split_1.refresh_from_db()
        split_2.refresh_from_db()

        assert split_1.status == RoyaltySplit.STATUS_ARCHIVED
        assert split_2.status == RoyaltySplit.STATUS_ACTIVE
        assert split_1.end_date == date(2020, 1, 31)
        assert split_2.start_date == date(2020, 2, 1)
        assert split_2.end_date is None

    @responses.activate
    def test_revision_is_confirmed_return_true_for_active(self):
        add_zendesk_mock_post_response()

        RoyaltySplitFactory(
            user=self.user,
            song=self.song,
            start_date=timezone.now().today(),
            rate=0.5,
            status=RoyaltySplit.STATUS_CONFIRMED,
            revision=1,
        )
        RoyaltySplitFactory(
            user=self.user2,
            song=self.song,
            start_date=timezone.now().today(),
            rate=0.5,
            status=RoyaltySplit.STATUS_CONFIRMED,
            revision=1,
        )

        splits = RoyaltySplit.objects.filter(revision=1)
        assert splits.revision_is_confirmed()

    @responses.activate
    def test_revision_is_confirmed_return_false_for_inactive(self):
        add_zendesk_mock_post_response()

        RoyaltySplitFactory(
            user=self.user,
            song=self.song,
            start_date=timezone.now().today(),
            rate=0.5,
            status=RoyaltySplit.STATUS_CONFIRMED,
            revision=1,
        )
        RoyaltySplitFactory(
            user=self.user2,
            song=self.song,
            start_date=timezone.now().today(),
            rate=0.5,
            status=RoyaltySplit.STATUS_PENDING,
            revision=1,
        )

        splits = RoyaltySplit.objects.filter(revision=1)
        assert splits.revision_is_confirmed() is False

    @responses.activate
    def test_are_same_revision_raises_error_with_mixed_revisions(self):
        add_zendesk_mock_post_response()

        RoyaltySplitFactory(
            user=self.user,
            song=self.song,
            start_date=timezone.now().today(),
            rate=1.0,
            status=RoyaltySplit.STATUS_CONFIRMED,
            revision=1,
        )
        RoyaltySplitFactory(
            user=self.user2,
            song=self.song,
            start_date=timezone.now().today(),
            rate=1.0,
            status=RoyaltySplit.STATUS_PENDING,
            revision=2,
        )

        splits = RoyaltySplit.objects.all()

        with pytest.raises(RoyaltySplitDifferentRevisionsError):
            splits.activate()

        with pytest.raises(RoyaltySplitDifferentRevisionsError):
            splits.archive()

        with pytest.raises(RoyaltySplitDifferentRevisionsError):
            splits.revision_is_confirmed()

    @responses.activate
    def test_are_same_revision_raises_error_with_mixed_songs(self):
        add_zendesk_mock_post_response()

        song2 = SongFactory()

        RoyaltySplitFactory(
            user=self.user,
            song=self.song,
            start_date=timezone.now().today(),
            rate=1.0,
            status=RoyaltySplit.STATUS_CONFIRMED,
            revision=1,
        )
        RoyaltySplitFactory(
            user=self.user2,
            song=song2,
            start_date=timezone.now().today(),
            rate=1.0,
            status=RoyaltySplit.STATUS_PENDING,
            revision=1,
        )

        splits = RoyaltySplit.objects.all()

        with pytest.raises(RoyaltySplitDifferentRevisionsError):
            splits.activate()

        with pytest.raises(RoyaltySplitDifferentRevisionsError):
            splits.archive()

        with pytest.raises(RoyaltySplitDifferentRevisionsError):
            splits.revision_is_confirmed()

    @responses.activate
    def test_last_revision_returns_correct_splits(self):
        RoyaltySplitFactory(user=self.user, song=self.song, revision=1)

        splits = RoyaltySplit.objects.last_revision(song_id=self.song.id)
        assert splits.count() == 1
        assert splits[0].revision == 1

        RoyaltySplitFactory(user=self.user, song=self.song, revision=2)
        RoyaltySplitFactory(user=self.user2, song=self.song, revision=2)

        splits = RoyaltySplit.objects.last_revision(song_id=self.song.id)
        assert splits.count() == 2
        assert splits[0].revision == 2
        assert splits[1].revision == 2

        RoyaltySplitFactory(user=self.user, song=self.song, revision=3)
        RoyaltySplitFactory(user=self.user2, song=self.song, revision=3)
        RoyaltySplitFactory(user=None, song=self.song, revision=3)

        splits = RoyaltySplit.objects.last_revision(song_id=self.song.id)
        assert splits.count() == 3
        assert splits[0].revision == 3
        assert splits[1].revision == 3
        assert splits[2].revision == 3

    @responses.activate
    def test_get_invalid_true_owner_splits(self):
        split_1 = RoyaltySplitFactory(user=self.user, song=self.song, revision=1)
        split_2 = RoyaltySplitFactory(user=self.user2, song=self.song, revision=1)

        assert split_2.is_owner is False
        assert RoyaltySplit.objects.invalid_true_owner().count() == 0

        split_2.is_owner = True
        split_2.save()

        assert RoyaltySplit.objects.invalid_true_owner().count() == 1

    @responses.activate
    def test_get_invalid_true_owner_splits_detects_no_user(self):
        split_1 = RoyaltySplitFactory(user=self.user, song=self.song, revision=1)
        split_2 = RoyaltySplitFactory(user=self.user2, song=self.song, revision=1)

        assert RoyaltySplit.objects.invalid_true_owner().count() == 0

        split_1.user = None
        split_1.save()

        assert RoyaltySplit.objects.invalid_true_owner().count() == 1

    @responses.activate
    def test_get_invalid_false_owner_splits(self):
        split_1 = RoyaltySplitFactory(user=self.user, song=self.song, revision=1)
        split_2 = RoyaltySplitFactory(user=self.user2, song=self.song, revision=1)

        assert split_1.is_owner is True
        assert RoyaltySplit.objects.invalid_false_owner().count() == 0

        split_1.is_owner = False
        split_1.save()

        assert RoyaltySplit.objects.invalid_false_owner().count() == 1
