import hashlib
import io

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from factory import Faker

from releases.models import CoverArt
from releases.tests.factories import CoverArtFactory


class CoverArtChecksumTestCase(TestCase):
    def test_checksum_is_set_after_saving(self):
        file_content = Faker('pystr').generate(extra_kwargs={}).encode()
        file_checksum = hashlib.md5(file_content).hexdigest()

        cover_art = CoverArtFactory(file__from_file=io.BytesIO(file_content))

        ca = CoverArt.objects.get(pk=cover_art.id)

        self.assertEqual(file_checksum, ca.checksum)

    def test_checksum_changed_if_image_is_updated(self):
        cover_art = CoverArtFactory(
            file__from_file=io.BytesIO(
                Faker('pystr').generate(extra_kwargs={}).encode()
            )
        )

        file_content = Faker('pystr').generate(extra_kwargs={}).encode()
        file_checksum = hashlib.md5(file_content).hexdigest()

        ca = CoverArt.objects.get(pk=cover_art.id)
        ca.file = SimpleUploadedFile(name=ca.file.name, content=file_content)
        ca.save()

        ca.refresh_from_db()

        self.assertEqual(file_checksum, ca.checksum)

    def test_checksum_not_calculated_for_empty_file(self):
        cover_art = CoverArtFactory(file=None)

        ca = CoverArt.objects.get(pk=cover_art.id)

        self.assertIsNone(ca.checksum)
