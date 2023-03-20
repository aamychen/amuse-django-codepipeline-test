from unittest import mock

from django.core.management import call_command
from django.test import TestCase

from releases.models import Release, SongFile
from releases.tests.factories import ReleaseFactory, SongFactory, SongFileFactory


class FixChecksumTestCase(TestCase):
    @mock.patch('amuse.tasks.zendesk_create_or_update_user')
    def setUp(self, mock_zendesk):
        self.release = ReleaseFactory(status=Release.STATUS_APPROVED)
        self.song = SongFactory(release=self.release)
        self.song_file = SongFileFactory(song=self.song, type=SongFile.TYPE_FLAC)

    def test_fix_checksum(self):
        SongFile.objects.filter(pk=self.song_file.pk).update(checksum=None)
        call_command("fix_checksums", "--limit=10")

        self.song_file.refresh_from_db()
        assert self.song_file.checksum

    def test_skip_deleted_releases(self):
        SongFile.objects.filter(pk=self.song_file.pk).update(checksum=None)
        self.release.status = Release.STATUS_DELETED
        self.release.save()

        call_command("fix_checksums", "--limit=10")

        self.song_file.refresh_from_db()
        assert self.song_file.checksum is None

    @mock.patch("releases.management.commands.fix_checksums.save_song_file_checksum")
    def test_dryrun(self, mock_save):
        SongFile.objects.filter(pk=self.song_file.pk).update(checksum=None)
        call_command("fix_checksums", "--limit=10", "--dryrun")

        self.song_file.refresh_from_db()
        assert self.song_file.checksum is None
        mock_save.assert_not_called()
