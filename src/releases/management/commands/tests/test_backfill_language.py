from unittest import mock

from django.core.management import call_command

from amuse.tests.test_api.base import AmuseAPITestCase
from codes.tests.factories import MetadataLanguageFactory
from releases.tests.factories import ReleaseFactory, SongFactory
from users.tests.factories import UserFactory


class BackfillMissingLanguagesTestCase(AmuseAPITestCase):
    @mock.patch('amuse.tasks.zendesk_create_or_update_user')
    def setUp(self, mock_zendesk):
        self.language = MetadataLanguageFactory()

        self.user = UserFactory()
        self.release = ReleaseFactory(pk=1, user=self.user, meta_language=None)
        self.song = SongFactory(
            pk=1, release=self.release, meta_language=None, meta_audio_locale=None
        )
        self.release_2 = ReleaseFactory(
            pk=2, user=self.user, meta_language=self.language
        )
        self.song_2 = SongFactory(
            pk=2,
            release=self.release_2,
            meta_language=self.language,
            meta_audio_locale=self.language,
        )

    def test_backfill_release_missing_language_dryrun(self):
        call_command(
            "backfill_language",
            "--type=release_language",
            f"--language_id={self.language.pk}",
            "--dry-run",
        )

        self.release.refresh_from_db()
        self.song.refresh_from_db()
        self.release_2.refresh_from_db()
        self.song_2.refresh_from_db()

        assert self.release.meta_language is None
        assert self.song.meta_language is None
        assert self.song.meta_audio_locale is None
        assert self.release_2.meta_language == self.language
        assert self.song_2.meta_language == self.language
        assert self.song_2.meta_audio_locale == self.language

    def test_backfill_release_missing_language_limit(self):
        call_command(
            "backfill_language",
            "--type=release_language",
            f"--language_id={self.language.pk}",
            "--limit=1",
        )

        self.release.refresh_from_db()
        self.song.refresh_from_db()
        self.release_2.refresh_from_db()
        self.song_2.refresh_from_db()

        assert self.release.meta_language == self.language
        assert self.song.meta_language is None
        assert self.song.meta_audio_locale is None
        assert self.release_2.meta_language == self.language
        assert self.song_2.meta_language == self.language
        assert self.song_2.meta_audio_locale == self.language

    def test_backfill_release_missing_language(self):
        call_command(
            "backfill_language",
            "--type=release_language",
            f"--language_id={self.language.pk}",
        )

        self.release.refresh_from_db()
        self.song.refresh_from_db()
        self.release_2.refresh_from_db()
        self.song_2.refresh_from_db()

        assert self.release.meta_language == self.language
        assert self.song.meta_language is None
        assert self.song.meta_audio_locale is None
        assert self.release_2.meta_language == self.language
        assert self.song_2.meta_language == self.language
        assert self.song_2.meta_audio_locale == self.language

    def test_backfill_song_missing_language(self):
        call_command(
            "backfill_language",
            "--type=song_language",
            f"--language_id={self.language.pk}",
        )

        self.release.refresh_from_db()
        self.song.refresh_from_db()
        self.release_2.refresh_from_db()
        self.song_2.refresh_from_db()

        assert self.release.meta_language is None
        assert self.song.meta_language == self.language
        assert self.song.meta_audio_locale is None
        assert self.release_2.meta_language == self.language
        assert self.song_2.meta_language == self.language
        assert self.song_2.meta_audio_locale == self.language

    def test_backfill_song_missing_locale(self):
        call_command(
            "backfill_language",
            "--type=song_locale",
            f"--language_id={self.language.pk}",
        )

        self.release.refresh_from_db()
        self.song.refresh_from_db()
        self.release_2.refresh_from_db()
        self.song_2.refresh_from_db()

        assert self.release.meta_language is None
        assert self.song.meta_language is None
        assert self.song.meta_audio_locale == self.language
        assert self.release_2.meta_language == self.language
        assert self.song_2.meta_language == self.language
        assert self.song_2.meta_audio_locale == self.language
