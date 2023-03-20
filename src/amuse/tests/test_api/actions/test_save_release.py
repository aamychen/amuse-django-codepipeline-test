from unittest import mock

from amuse.api.actions.release import save_release
from amuse.tests.test_api.base import AmuseAPITestCase
from releases.tests.factories import ReleaseFactory, SongFactory, GenreFactory
from users.models import User
from users.tests.factories import UserFactory


class SaveReleaseTestCase(AmuseAPITestCase):
    def setUp(self):
        self.user = UserFactory(category=User.CATEGORY_DEFAULT)
        self.release = ReleaseFactory(user=self.user)
        self.song = SongFactory(release=self.release)

    @mock.patch('releases.models.release.Release.save')
    def test_calls_save_release(self, mock_release_save):
        save_release(self.release)
        assert mock_release_save.called

    @mock.patch('releases.models.release.Release.save')
    @mock.patch('amuse.api.actions.release.enforce_release_version')
    def test_calls_enforce_release_version(self, mock_enforce_release_version, _):
        save_release(self.release)
        assert mock_enforce_release_version.called

    @mock.patch('releases.models.release.Release.save')
    @mock.patch('releases.models.release.Release.get_most_occuring_genre')
    def test_sets_genre_to_get_most_occuring_genre_response(
        self, mock_release_get_most_occuring_genre, _
    ):
        expected_genre = GenreFactory()
        mock_release_get_most_occuring_genre.return_value = expected_genre

        save_release(self.release)
        assert mock_release_get_most_occuring_genre.called
        self.assertEqual(self.release.genre, expected_genre)

    @mock.patch('releases.models.release.Release.save')
    @mock.patch(
        'amuse.api.actions.release.exclude_youtube_content_id_for_disallowed_genres'
    )
    def test_calls_exclude_youtube_content_id_for_disallowed_genres_when_non_priority_user_(
        self, mocked_exclude_youtube_for_genres, _
    ):
        save_release(self.release)
        mocked_exclude_youtube_for_genres.assert_called_once_with(self.release)

    @mock.patch('releases.models.release.Release.save')
    @mock.patch(
        'amuse.api.actions.release.exclude_youtube_content_id_for_disallowed_genres'
    )
    def test_does_not_call_exclude_youtube_content_id_for_disallowed_genres_when_priority_user(
        self, mocked_exclude_youtube_for_genres, _
    ):
        self.user.category = User.CATEGORY_PRIORITY
        self.user.save()
        self.user.refresh_from_db()

        save_release(self.release)
        assert not mocked_exclude_youtube_for_genres.called
