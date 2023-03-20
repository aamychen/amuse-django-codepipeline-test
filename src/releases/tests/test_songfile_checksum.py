import hashlib

from django.test import TestCase
from factory import Faker

from releases.models import SongFile
from releases.tests.factories import SongFileFactory


class SongFileChecksumTestCase(TestCase):
    def test_checksum_is_set_after_saving(self):
        song_file = SongFileFactory(type=SongFile.TYPE_FLAC)
        file_checksum = hashlib.md5(song_file.file.read()).hexdigest()

        sf = SongFile.objects.get(pk=song_file.id)

        self.assertIsNone(song_file.checksum)
        self.assertEqual(sf.checksum, file_checksum)

    def test_checksum_not_changed_if_checksum_is_already_set(self):
        file_content = Faker('pystr').generate(extra_kwargs={}).encode()

        expected_checksum = 'checksum_already_set'
        song_file = SongFileFactory(
            type=SongFile.TYPE_FLAC, file__data=file_content, checksum=expected_checksum
        )

        sf = SongFile.objects.get(pk=song_file.id)

        self.assertEqual(sf.checksum, expected_checksum)

    def test_checksum_not_calculated_for_empty_file(self):
        song_file = SongFileFactory(type=SongFile.TYPE_FLAC, file=None)

        sf = SongFile.objects.get(pk=song_file.id)

        self.assertIsNone(sf.checksum)
