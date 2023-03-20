from datetime import date, timedelta, datetime
from unittest.mock import patch

from django.conf import settings
from django.test import TestCase
from factory import Faker
from oauth2client.client import FlowExchangeError

from releases.models import ReleaseArtistRole
from releases.models.song import Song, SongFile
from releases.tests.factories import (
    GenreFactory,
    ReleaseArtistRoleFactory,
    ReleaseFactory,
    SongFactory,
    SongFileFactory,
    StoreFactory,
)
from releases.utils import (
    default_label_name,
    default_original_release_date,
    filter_song_file_flac,
    filter_song_file_mp3,
    queue_celery_tasks,
    release_explicit,
    split_genres,
    parse_label,
    get_upcoming_releases,
    ordered_stores_queryset,
)
from users.tests.factories import Artistv2Factory


class ReleaseUtilsTestCase(TestCase):
    def test_split_genres(self):
        genre1 = GenreFactory()
        genre2 = GenreFactory(parent=genre1)
        self.assertEqual(split_genres(genre1), (genre1, None))
        self.assertEqual(split_genres(genre2), (genre1, genre2))

    def test_release_explicit(self):
        release1 = ReleaseFactory()
        song1 = SongFactory(explicit=Song.EXPLICIT_TRUE, release=release1)
        release2 = ReleaseFactory()
        song2 = SongFactory(explicit=Song.EXPLICIT_FALSE, release=release2)
        release3 = ReleaseFactory()
        song3 = SongFactory(explicit=Song.EXPLICIT_TRUE, release=release3)
        song4 = SongFactory(explicit=Song.EXPLICIT_FALSE, release=release3)

        self.assertEqual(release_explicit(release1), 'explicit')
        self.assertEqual(release_explicit(release2), 'none')
        self.assertEqual(release_explicit(release3), 'explicit')

    def test_default_original_release_date(self):
        release1 = ReleaseFactory()
        release2 = ReleaseFactory(
            original_release_date=date.today() - timedelta(weeks=100)
        )

        self.assertEqual(release1.release_date, default_original_release_date(release1))
        self.assertEqual(
            release2.original_release_date, default_original_release_date(release2)
        )

    def test_default_label_name(self):
        release1 = ReleaseFactory(label='')
        release2 = ReleaseFactory(label=Faker('word'))
        artistv2 = Artistv2Factory(name=f'DJ Artist')
        ReleaseArtistRoleFactory(
            release=release1,
            artist=artistv2,
            role=ReleaseArtistRole.ROLE_PRIMARY_ARTIST,
            main_primary_artist=True,
        )
        self.assertEqual(default_label_name(release1), artistv2.name)
        self.assertEqual(default_label_name(release2), release2.label)

    def test_filter_song_file_flac(self):
        song = SongFactory()
        song_file_flac = SongFileFactory(song=song, type=SongFile.TYPE_FLAC)
        song_file_mp3 = SongFileFactory(song=song, type=SongFile.TYPE_MP3)
        self.assertEqual(filter_song_file_flac(song), song_file_flac)

    def test_filter_song_file_mp3(self):
        song = SongFactory()
        song_file_flac = SongFileFactory(song=song, type=SongFile.TYPE_FLAC)
        song_file_mp3 = SongFileFactory(song=song, type=SongFile.TYPE_MP3)
        self.assertEqual(filter_song_file_mp3(song), song_file_mp3)

    @patch("amuse.tasks.zendesk_create_or_update_user")
    def test_parse_label_returns_label_if_it_exists(self, mock_zendesk):
        release = ReleaseFactory(label="something")
        artistv2 = Artistv2Factory(name=f'DJ Artist')
        ReleaseArtistRoleFactory(
            release=release,
            artist=artistv2,
            role=ReleaseArtistRole.ROLE_PRIMARY_ARTIST,
            main_primary_artist=True,
        )
        assert parse_label(release) == release.label

    @patch("amuse.tasks.zendesk_create_or_update_user")
    def test_parse_label_returns_main_primary_artist_name_if_label_is_none(
        self, mock_zendesk
    ):
        release = ReleaseFactory(label=None)
        artistv2 = Artistv2Factory(name=f'DJ Artist')
        ReleaseArtistRoleFactory(
            release=release,
            artist=artistv2,
            role=ReleaseArtistRole.ROLE_PRIMARY_ARTIST,
            main_primary_artist=True,
        )
        assert parse_label(release) == release.main_primary_artist.name

    @patch("amuse.tasks.zendesk_create_or_update_user")
    def test_parse_label_returns_main_primary_artist_name_if_label_is_zero_length(
        self, mock_zendesk
    ):
        release = ReleaseFactory(label="")
        artistv2 = Artistv2Factory(name=f'DJ Artist')
        ReleaseArtistRoleFactory(
            release=release,
            artist=artistv2,
            role=ReleaseArtistRole.ROLE_PRIMARY_ARTIST,
            main_primary_artist=True,
        )
        assert parse_label(release) == release.main_primary_artist.name

    def test_get_upcoming_releases_without_link(self):
        tommorow = datetime.now() + timedelta(days=1)
        ReleaseFactory.create_batch(10, release_date=tommorow, link=None)
        releases = get_upcoming_releases(days_to_release=5, has_link=False)
        assert len(releases) == 10

    def test_ordered_stores_queryset(self):
        audiomack = StoreFactory(
            name='Audiomack',
            internal_name='audiomack',
            admin_active=True,
            active=True,
            is_pro=False,
            show_on_top=False,
        )
        spotify = StoreFactory(
            name='Spotify',
            internal_name='spotify',
            admin_active=True,
            active=True,
            is_pro=False,
            show_on_top=True,
        )
        apple = StoreFactory(
            name='Apple',
            internal_name='apple',
            admin_active=True,
            active=True,
            is_pro=False,
            show_on_top=True,
        )
        youtube_music = StoreFactory(
            name='Youtube Music',
            internal_name='youtube_music',
            admin_active=True,
            active=True,
            is_pro=False,
            show_on_top=True,
        )
        pandora = StoreFactory(
            name='Pandora',
            internal_name='pandora',
            admin_active=True,
            active=True,
            is_pro=False,
            show_on_top=False,
        )
        disco = StoreFactory(
            name='DISCO',
            internal_name='disco',
            admin_active=True,
            active=False,
            is_pro=False,
            show_on_top=False,
        )
        tiktok = StoreFactory(
            name='Tiktok',
            internal_name='tiktok',
            admin_active=True,
            active=True,
            is_pro=True,
            show_on_top=False,
        )

        stores = ordered_stores_queryset()

        expected_list = [
            apple,
            spotify,
            youtube_music,
            tiktok,
            audiomack,
            pandora,
            disco,
        ]
        self.assertListEqual([store for store in stores], expected_list)

    def test_ordered_stores_queryset_with_exclude(self):
        audiomack = StoreFactory(
            name='Audiomack',
            internal_name='audiomack',
            admin_active=True,
            active=True,
            is_pro=False,
            show_on_top=False,
        )
        spotify = StoreFactory(
            name='Spotify',
            internal_name='spotify',
            admin_active=True,
            active=True,
            is_pro=False,
            show_on_top=True,
        )
        apple = StoreFactory(
            name='Apple',
            internal_name='apple',
            admin_active=True,
            active=True,
            is_pro=False,
            show_on_top=True,
        )
        youtube_music = StoreFactory(
            name='Youtube Music',
            internal_name='youtube_music',
            admin_active=True,
            active=True,
            is_pro=False,
            show_on_top=True,
        )
        pandora = StoreFactory(
            name='Pandora',
            internal_name='pandora',
            admin_active=True,
            active=True,
            is_pro=False,
            show_on_top=False,
        )
        disco = StoreFactory(
            name='DISCO',
            internal_name='disco',
            admin_active=True,
            active=False,
            is_pro=False,
            show_on_top=False,
        )
        tiktok = StoreFactory(
            name='Tiktok',
            internal_name='tiktok',
            admin_active=True,
            active=True,
            is_pro=True,
            show_on_top=False,
        )

        stores = ordered_stores_queryset(exclude_stores=[audiomack.internal_name])

        expected_list = [apple, spotify, youtube_music, tiktok, pandora, disco]
        self.assertListEqual([store for store in stores], expected_list)


class QueueTasksTestCase(TestCase):
    @patch('amuse.tasks.logger.warning')
    @patch('amuse.tasks.switch_is_active', return_value=False)
    @patch('amuse.tasks.GoogleDriveSongFileDownload.get_download_link')
    def test_google_drive_to_bucket_oauth_error_aborts_chain(
        self, mock_get_download_link, mock_switch, mock_log_warning
    ):
        file_name = 'gdrive_file'
        error = FlowExchangeError()
        mock_get_download_link.side_effect = error
        song = None
        with patch('amuse.tasks.zendesk_create_or_update_user'):
            song = SongFactory()

        queue_celery_tasks(song.pk, None, None, 'gdrive_code', file_name, 'wav')

        mock_log_warning.assert_called_with(
            'Google drive to bucket %s OAuth2 error for file_id %s: %s',
            settings.AWS_SONG_FILE_UPLOADED_BUCKET_NAME,
            file_name,
            error,
        )
        mock_switch.assert_not_called()
