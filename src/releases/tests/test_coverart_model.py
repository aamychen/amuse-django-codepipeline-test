from os.path import join
from unittest.mock import patch

import pytest
from django.conf import settings
from django.test import TestCase
from PIL import Image
from simple_history.manager import HistoryManager

from amuse.tests.factories import ImageFactory
from releases.models import CoverArt, Release, cover_art_file_changed
from releases.tests.factories import CoverArtFactory, ReleaseFactory


class CoverArtTestCase(TestCase):
    @patch('amuse.vendor.zendesk.api.create_or_update_user')
    def test_coverart_history(self, mocked_zendesk):
        """CoverArt model history is enabled."""
        coverart = CoverArt()
        self.assertTrue(isinstance(coverart.history, HistoryManager))
        self.assertEqual(coverart.history.count(), 0)

        coverart = CoverArtFactory()
        self.assertEqual(coverart.history.count(), 1)

    @patch('amuse.vendor.zendesk.api.create_or_update_user')
    def test_coverart_images(self, mocked_zendesk):
        coverart = CoverArtFactory()

        images = [ImageFactory(), ImageFactory()]

        coverart.images.set(images)

        coverart = CoverArt.objects.get(id=coverart.id)

        images_retrieved = coverart.images.all()
        assert len(images_retrieved) == 2
        assert images[0] in images_retrieved
        assert images[1] in images_retrieved

    @patch('amuse.vendor.zendesk.api.create_or_update_user')
    def test_cover_art_file_changed(self, mocked_zendesk):
        release = ReleaseFactory()

        cover_art_file_changed(release)
        release.refresh_from_db()
        assert release.status == Release.STATUS_PENDING


@pytest.mark.django_db
@pytest.mark.parametrize(
    'file_name', ('releases/tests/cmyk.jpg', 'releases/tests/cmyk_no_icc_profile.jpg')
)
def test_convert_cmyk_to_rgb(file_name):
    file_path = join(settings.BASE_DIR, file_name)
    assert Image.open(file_path).mode == 'CMYK'

    with patch('amuse.vendor.zendesk.api.create_or_update_user'):
        coverart = CoverArtFactory(file__from_path=file_path, file__filename='cmyk.jpg')

    coverart.refresh_from_db()
    assert Image.open(coverart.file).mode == 'RGB'

    # Ensure RGB image not converted
    with patch('releases.models.coverart.CoverArt.save_jpeg_image') as mocked_save:
        coverart.save()

    mocked_save.assert_not_called()


@pytest.mark.django_db
def test_convert_png_to_jpg():
    file_path = join(
        settings.BASE_DIR, 'amuse/tests/test_tasks/fixtures/amuse-cover.jpg'
    )
    assert Image.open(file_path).format == 'PNG'

    with patch('amuse.vendor.zendesk.api.create_or_update_user'):
        coverart = CoverArtFactory(file__from_path=file_path, file__filename='png.jpg')

    coverart.refresh_from_db()
    assert Image.open(coverart.file).format == 'JPEG'


@pytest.mark.django_db
def test_pil_transform_error():
    file_path = join(settings.BASE_DIR, 'releases/tests/sample.jpg')

    with patch('amuse.vendor.zendesk.api.create_or_update_user'):
        coverart = CoverArtFactory(
            file__from_path=file_path, file__filename='sample.jpg'
        )

    coverart.refresh_from_db()
    assert Image.open(coverart.file).format == 'JPEG'


@pytest.mark.django_db
def test_pil_truncated_file():
    file_path = join(settings.BASE_DIR, 'releases/tests/truncated.jpg')

    with patch('amuse.vendor.zendesk.api.create_or_update_user'):
        coverart = CoverArtFactory(
            file__from_path=file_path, file__filename='truncated.jpg'
        )

    coverart.refresh_from_db()
    assert coverart.get_file_image() is None


@pytest.mark.django_db
def test_file_ending_always_jpeg():
    file_path = join(
        settings.BASE_DIR, 'amuse/tests/test_tasks/fixtures/amuse-cover.jpg'
    )

    with patch('amuse.vendor.zendesk.api.create_or_update_user'):
        coverart = CoverArtFactory(file__from_path=file_path, file__filename='no.png')

    coverart.refresh_from_db()
    assert coverart.file.name.endswith('.jpg')


@pytest.mark.django_db
def test_rgb_jpeg_with_wrong_file_ending_is_renamed():
    file_path = join(settings.BASE_DIR, 'releases/tests/jpeg.png')

    with patch('amuse.vendor.zendesk.api.create_or_update_user'):
        coverart = CoverArtFactory(file__from_path=file_path, file__filename='no.png')

    coverart.refresh_from_db()
    assert coverart.file.name.endswith('.jpg')
