import responses
from decimal import Decimal

from django.core.management import call_command
from django.test import TestCase, override_settings

from amuse.tests.helpers import (
    add_zendesk_mock_post_response,
    ZENDESK_MOCK_API_URL_TOKEN,
)

from releases.models import Release, Song, RoyaltySplit
from releases.tests.factories import SongFactory, RoyaltySplitFactory
from users.models import User
from users.tests.factories import UserFactory


@override_settings(**ZENDESK_MOCK_API_URL_TOKEN)
class MigrateDealsToSplitsTestCase(TestCase):
    @responses.activate
    def setUp(self):
        add_zendesk_mock_post_response()

        for i in range(5):
            SongFactory()

        user = UserFactory()
        song = Song.objects.first()
        RoyaltySplitFactory(user=user, song=song)

    def test_only_migrates_songs_that_doesnt_have_royalty_splits(self):
        assert RoyaltySplit.objects.count() == 1
        call_command('migrate_deals_to_splits')
        assert RoyaltySplit.objects.count() == 5

    def test_sets_correct_values_for_royalty_splits(self):
        call_command('migrate_deals_to_splits')

        royalty_splits = list(
            RoyaltySplit.objects.filter(status=RoyaltySplit.STATUS_ACTIVE).values(
                "song_id", "user_id", "rate", "start_date"
            )
        )

        songs = list(
            Song.objects.all()[1:].values("id", "release__user__id", "release__created")
        )

        for song, royalty_split in zip(songs, royalty_splits):
            assert song["id"] == royalty_split["song_id"]
            assert song["release__user__id"] == royalty_split["user_id"]
            assert song["release__created"].date() == royalty_split["start_date"]
            assert royalty_split["rate"] == Decimal("1.00")
