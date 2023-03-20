import responses
from io import StringIO
from unittest import mock
from django.core.management import call_command
from django.test import TestCase
from releases.models import ReleaseArtistRole
from releases.models import SongArtistRole, Release, Song
from users.tests.factories import Artistv2Factory
from releases.tests.factories import (
    ReleaseFactory,
    SongFactory,
    SongArtistRoleFactory,
    ReleaseArtistRoleFactory,
)
from releases.management.commands import updateartistsequence


class UpdateArtistSequenceTestCase(TestCase):
    @responses.activate
    @mock.patch(
        'releases.management.commands.updateartistsequence.update_rar', autospec=True
    )
    def test_update_rar(self, mock_update_rar):
        updateartistsequence.update_rar(to_release_id=111)
        mock_update_rar.assert_called_once_with(111)

    @responses.activate
    @mock.patch(
        'releases.management.commands.updateartistsequence.add_songs_to_queue',
        autospec=True,
    )
    def test_add_songs_to_queue(self, mock_add_songs_to_queue):
        from queue import Queue

        q = Queue()
        updateartistsequence.add_songs_to_queue(queue=q, to_release_id=11)
        mock_add_songs_to_queue.assert_called_once_with(q, 11)

    @responses.activate
    @mock.patch(
        'releases.management.commands.updateartistsequence.update_sar_artist_sequence',
        autospec=True,
    )
    def test_add_songs_to_queue(self, mock_update_sar_artist_sequence):
        from queue import Queue

        q = Queue()
        updateartistsequence.update_sar_artist_sequence(queue=q, total=10, test=False)
        mock_update_sar_artist_sequence.assert_called_once_with(q, 10, False)

    @responses.activate
    def test_default_options(self):
        release = ReleaseFactory()
        song = SongFactory(release=release)
        artist_primary = Artistv2Factory(name="John", owner=release.user)
        featured_artist = Artistv2Factory(name="Featured")
        writer_artist = Artistv2Factory(name="Writer")
        second_primary = Artistv2Factory(name="SecondPrimary")

        # Add data to sar and rar without artist_sequence
        rar = ReleaseArtistRoleFactory(
            release=release,
            artist=artist_primary,
            role=ReleaseArtistRole.ROLE_PRIMARY_ARTIST,
        )
        sar_p = SongArtistRoleFactory(
            song=song, artist=artist_primary, role=SongArtistRole.ROLE_PRIMARY_ARTIST
        )
        sar_p2 = SongArtistRoleFactory(
            song=song, artist=second_primary, role=SongArtistRole.ROLE_PRIMARY_ARTIST
        )
        sar_f = SongArtistRoleFactory(
            song=song, artist=featured_artist, role=SongArtistRole.ROLE_FEATURED_ARTIST
        )
        sar_w = SongArtistRoleFactory(
            song=song, artist=writer_artist, role=SongArtistRole.ROLE_WRITER
        )

        out = StringIO()
        call_command(
            'updateartistsequence', '--confirm=yes', '--test_mode=True', stdout=out
        )
        rar.refresh_from_db()
        sar_p.refresh_from_db()
        sar_p2.refresh_from_db()
        sar_f.refresh_from_db()
        sar_w.refresh_from_db()

        # Assert artist_sequence added
        self.assertEqual(rar.artist_sequence, 1)
        self.assertEqual(sar_p.artist_sequence, 1)
        self.assertEqual(sar_p2.artist_sequence, 2)
        self.assertEqual(sar_f.artist_sequence, 3)
        self.assertEqual(sar_w.artist_sequence, 4)
