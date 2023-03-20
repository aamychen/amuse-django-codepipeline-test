import logging
from datetime import datetime, timedelta
from unittest import mock
from django.test import TestCase, override_settings
from amuse.tests.helpers import (
    add_zendesk_mock_post_response,
    ZENDESK_MOCK_API_URL_TOKEN,
)
from amuse.vendor.spotify.cron import (
    backfill_eligible_users,
    fetch_users_eligible_for_backfill,
    filter_related_users,
    get_prepared_users,
)
from releases.models.release import Release
from releases.tests.factories import ReleaseFactory
from users.tests.factories import UserFactory


@override_settings(**ZENDESK_MOCK_API_URL_TOKEN)
class SlayerCronTestCase(TestCase):
    def setUp(self):
        logging.disable(logging.CRITICAL)

    def test_fetch_users_eligible_for_backfill_only_users_with_no_spotify_id(self):
        add_zendesk_mock_post_response()
        user0 = UserFactory(spotify_id=None)
        user1 = UserFactory(spotify_id="test123")
        ReleaseFactory(
            user=user0, status=Release.STATUS_RELEASED, release_date=datetime.today()
        )
        ReleaseFactory(
            user=user1, status=Release.STATUS_RELEASED, release_date=datetime.today()
        )

        assert len(fetch_users_eligible_for_backfill()) == 1

    def test_fetch_users_eligible_for_backfill_only_users_with_released_releases(self):
        add_zendesk_mock_post_response()
        user0 = UserFactory(spotify_id=None)
        user1 = UserFactory(spotify_id=None)
        ReleaseFactory(
            user=user0, status=Release.STATUS_RELEASED, release_date=datetime.today()
        )
        ReleaseFactory(
            user=user1, status=Release.STATUS_APPROVED, release_date=datetime.today()
        )

        assert len(fetch_users_eligible_for_backfill()) == 1

    def test_fetch_users_eligible_for_backfill_only_users_with_release_date_lte_90(
        self,
    ):
        add_zendesk_mock_post_response()
        user0 = UserFactory(spotify_id=None)
        user1 = UserFactory(spotify_id=None)
        ReleaseFactory(
            user=user0, status=Release.STATUS_RELEASED, release_date=datetime.today()
        )
        ReleaseFactory(
            user=user1,
            status=Release.STATUS_RELEASED,
            release_date=datetime.today() - timedelta(days=91),
        )

        assert len(fetch_users_eligible_for_backfill()) == 1

    @mock.patch(
        "amuse.vendor.spotify.cron.fetch_users_eligible_for_backfill",
        return_value=list(range(0, 155)),
    )
    def test_backfill_eligible_users(self, _):
        add_zendesk_mock_post_response()
        user = UserFactory(spotify_id=None)
        with mock.patch(
            "amuse.vendor.spotify.cron.users_spotifyartist",
            return_value={
                "users_to_spotify_artists": [
                    {
                        "user_id": str(user.id),
                        "uri": "spotify:artist:test123",
                        "id": "test123",
                        "name": "Adel",
                        "popularity": "61",
                        "followers": "20654",
                        "genres": ["deep swedish hip hop"],
                        "url": "https://open.spotify.com/artist/test123",
                        "image_url": "https://i.scdn.co/image/1274fedb168b0c0267bcc6968e91faf0ccbc9635",
                    }
                ]
            },
        ):
            backfill_eligible_users()

        assert user.spotify_id == None
        user.refresh_from_db()
        assert user.spotify_id == "test123"

    @mock.patch('amuse.vendor.spotify.cron.users_spotifyartist')
    def test_filter_related_users_resolver_called(self, mock_fn):
        add_zendesk_mock_post_response()
        ids, chunk_size = ["Test"] * 20, 10
        mock_fn.return_value = {'users_to_spotify_artists': [{}]}
        users = filter_related_users(ids, chunk_size)
        users.__next__()
        mock_fn.assert_called_with(ids[:chunk_size])
        users.__next__()
        mock_fn.assert_called_with(ids[chunk_size:])
        self.assertEqual(len(mock_fn.mock_calls), len(ids) / chunk_size)

    @mock.patch('amuse.vendor.spotify.cron.users_spotifyartist')
    def test_filter_related_users_missing_body(self, mock_fn):
        add_zendesk_mock_post_response()
        mock_fn.return_value = None

        with self.assertRaises(StopIteration):
            filter_related_users([1], 1).__next__()

    @mock.patch('amuse.vendor.spotify.cron.users_spotifyartist')
    def test_filter_related_users_missing_key(self, mock_fn):
        add_zendesk_mock_post_response()
        mock_fn.return_value = {}

        with self.assertRaises(StopIteration):
            filter_related_users([1], 1).__next__()

    @mock.patch('amuse.vendor.spotify.cron.users_spotifyartist')
    def test_filter_related_users(self, mock_fn):
        add_zendesk_mock_post_response()
        ids, chunk_size = ["Test"] * 20, 10
        mock_fn.return_value = {'users_to_spotify_artists': [dict(id=1), dict(id=2)]}
        items = list(filter_related_users(ids, chunk_size))
        self.assertEqual(items[0]['id'], 1)
        self.assertEqual(items[1]['id'], 2)

    @mock.patch('amuse.vendor.spotify.cron.users_spotifyartist')
    def test_filter_prepared_users(self, mock_fn):
        add_zendesk_mock_post_response()
        chunk_size = 2
        amuse_spotify_users_map = [
            dict(user_id=100, id=10),
            dict(user_id=200, id=20),
        ]
        mock_fn.return_value = {'users_to_spotify_artists': amuse_spotify_users_map}
        amuse_users = {
            u['user_id']: UserFactory(id=u['user_id'], created=datetime.now())
            for u in amuse_spotify_users_map
            if u.keys() >= {'user_id', 'id'}
        }
        amuse_user_ids = sorted(list(amuse_users.keys()))
        result = list(get_prepared_users(amuse_user_ids, chunk_size))

        # Valid users should be contained in the result
        self.assertEqual(result[0].spotify_id, amuse_spotify_users_map[0]['id'])
        self.assertEqual(result[1].spotify_id, amuse_spotify_users_map[1]['id'])
