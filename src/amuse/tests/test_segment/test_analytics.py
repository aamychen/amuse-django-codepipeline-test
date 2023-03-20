import math

from amuse.analytics import create_event_data
from django.test import TestCase
from releases import utils
from releases.models import Release
from releases.tests.factories import ReleaseFactory, SongFactory


class AnalyticsTestCase(TestCase):
    def test_create_event_data_song_error(self):
        error_flag = utils.SONG_ALLOWED_FLAGS[1]

        release_with_song_error = ReleaseFactory()
        song = SongFactory(error_flags=error_flag, release=release_with_song_error)
        data = create_event_data(release_with_song_error)
        assert data == {
            "owner_id": release_with_song_error.user.id,
            "release_id": release_with_song_error.id,
            "release_name": release_with_song_error.name,
            "release_status": release_with_song_error.status,
            "main_primary_artist": release_with_song_error.main_primary_artist.name
            if release_with_song_error.main_primary_artist
            else "",
            "release_date": release_with_song_error.release_date,
            "release_flags": [],
            "songs_with_flags": [
                {
                    'song_id': song.pk,
                    'song_name': song.name,
                    'error_flags': ['explicit_lyrics'],
                }
            ],
            "schedule_type": "static",
        }

    def test_create_event_data_songs_errors(self):
        release_with_song_errors = ReleaseFactory()
        # 17 is the corresponding number of setting both flag 0 and 16 (allowed flags).
        song_1 = SongFactory(error_flags=17, release=release_with_song_errors)
        song_2 = SongFactory(
            error_flags=utils.SONG_ALLOWED_FLAGS[1], release=release_with_song_errors
        )

        song_1.error_flags.set_bit(0, True)
        song_2.error_flags.set_bit(4, True)
        data = create_event_data(release_with_song_errors)

        assert data == {
            "owner_id": release_with_song_errors.user.id,
            "release_id": release_with_song_errors.id,
            "release_name": release_with_song_errors.name,
            "release_status": release_with_song_errors.status,
            "main_primary_artist": release_with_song_errors.main_primary_artist.name
            if release_with_song_errors.main_primary_artist
            else "",
            "release_date": release_with_song_errors.release_date,
            "release_flags": [],
            "songs_with_flags": [
                {
                    'song_id': song_1.pk,
                    'song_name': song_1.name,
                    'error_flags': ['rights_samplings', 'explicit_lyrics'],
                },
                {
                    'song_id': song_2.pk,
                    'song_name': song_2.name,
                    'error_flags': ['explicit_lyrics'],
                },
            ],
            "schedule_type": "static",
        }

    def test_create_event_data_release_error(self):
        error_flag = utils.RELEASE_ALLOWED_FLAGS[1]
        release_with_error = ReleaseFactory(error_flags=error_flag)
        song = SongFactory(release=release_with_error)
        data = create_event_data(release_with_error)

        assert data == {
            "owner_id": release_with_error.user.id,
            "release_id": release_with_error.id,
            "release_name": release_with_error.name,
            "release_status": release_with_error.status,
            "main_primary_artist": release_with_error.main_primary_artist.name
            if release_with_error.main_primary_artist
            else "",
            "release_date": release_with_error.release_date,
            "release_flags": ['release_date-changed'],
            "songs_with_flags": [],
            "schedule_type": "static",
        }

    def test_create_event_data_release_errors(self):
        # 129 is the corresponding number of setting both flag 0 and 128 (allowed flags).
        release_with_error = ReleaseFactory(error_flags=129)
        song = SongFactory(release=release_with_error)
        data = create_event_data(release_with_error)

        assert data == {
            "owner_id": release_with_error.user.id,
            "release_id": release_with_error.id,
            "release_name": release_with_error.name,
            "release_status": release_with_error.status,
            "main_primary_artist": release_with_error.main_primary_artist.name
            if release_with_error.main_primary_artist
            else "",
            "release_date": release_with_error.release_date,
            "release_flags": ['artwork_social-media', 'release_date-changed'],
            "songs_with_flags": [],
            "schedule_type": "static",
        }
