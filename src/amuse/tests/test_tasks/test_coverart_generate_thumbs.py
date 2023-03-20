import responses

from amuse import tasks
from amuse.db.models import ImageWithThumbsFieldFile
from amuse.storages import S3Storage
from amuse.tests.factories import ImageFactory
from amuse.tests.helpers import (
    add_zendesk_mock_post_response,
    ZENDESK_MOCK_API_URL_TOKEN,
)
from django.conf import settings
from django.test import TestCase, override_settings
from releases.tests.factories import CoverArtFactory, ReleaseFactory
from unittest import mock


SOURCE_FILE_NAME = 'b03bcf60-e6ae-11e8-a8eb-c73a387ba237.jpg'


def create_storage():
    storage = S3Storage(bucket_name=settings.AWS_COVER_ART_UPLOADED_BUCKET_NAME)
    with storage.open(SOURCE_FILE_NAME, 'wb') as file:
        file.write(open('amuse/tests/test_tasks/fixtures/amuse-cover.jpg', 'rb').read())
    return storage


@responses.activate
@override_settings(**ZENDESK_MOCK_API_URL_TOKEN)
def create_coverart():
    add_zendesk_mock_post_response()
    release = ReleaseFactory()
    with mock.patch('releases.models.coverart.CoverArt.save_jpeg_image'):
        coverart = CoverArtFactory(file=SOURCE_FILE_NAME, release=release)
    return coverart


@override_settings(**ZENDESK_MOCK_API_URL_TOKEN)
class CoverartGenerateThumbsTaskTestCase(TestCase):
    def test_thumbs_saved_to_storage(self):
        storage = create_storage()
        coverart = create_coverart()

        assert storage.exists('b03bcf60-e6ae-11e8-a8eb-c73a387ba237.800x800.jpg')
        assert storage.exists('b03bcf60-e6ae-11e8-a8eb-c73a387ba237.400x400.jpg')
        assert storage.exists('b03bcf60-e6ae-11e8-a8eb-c73a387ba237.200x200.jpg')

    def test_thumbs_stored_in_db(self):
        create_storage()
        coverart = create_coverart()

        coverart.refresh_from_db()
        images = coverart.images.all()

        assert len(images) == 3
        assert images[0].path == 'b03bcf60-e6ae-11e8-a8eb-c73a387ba237.200x200.jpg'
        assert images[1].path == 'b03bcf60-e6ae-11e8-a8eb-c73a387ba237.400x400.jpg'
        assert images[2].path == 'b03bcf60-e6ae-11e8-a8eb-c73a387ba237.800x800.jpg'

    def test_thumbs_not_regenerated_if_exists(self):
        create_storage()
        coverart = create_coverart()
        images = [
            ImageFactory(width=800, height=800),
            ImageFactory(width=400, height=400),
            ImageFactory(width=200, height=200),
        ]
        coverart.images.set(images)

        with mock.patch.object(
            ImageWithThumbsFieldFile, 'generate_thumbnail'
        ) as mock_generate_thumb:
            coverart.save()
            assert not mock_generate_thumb.called
