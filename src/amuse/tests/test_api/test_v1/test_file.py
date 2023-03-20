from unittest import mock

from amuse.api.base.views.file import create_s3_client_from_storage
from ..base import AmuseAPITestCase
from users.tests.factories import UserFactory


class FileAPITestCase(AmuseAPITestCase):
    def test_presigned_post_requires_auth(self):
        response = self.client.post('/api/file/upload')
        self.assertEqual(response.status_code, 401)

    def test_presigned_post_requires_filename(self):
        user = UserFactory()
        self.client.force_authenticate(user=user)
        response = self.client.post(
            '/api/file/upload', {'type': 'cover-art'}, format='json'
        )

        self.assertEqual(response.status_code, 400)
        data = response.json()
        self.assertEqual(data['errors'][0], 'Filename with extension must be provided')

    def test_presigned_post_requires_type(self):
        user = UserFactory()
        self.client.force_authenticate(user=user)
        response = self.client.post(
            '/api/file/upload', {'filename': 'my-photo.png'}, format='json'
        )

        self.assertEqual(response.status_code, 400)
        data = response.json()
        self.assertEqual(
            data['errors'][0], 'Type must be set to either "audio-file" or "cover-art"'
        )

    def test_presigned_post_for_cover_art_jpeg(self):
        user = UserFactory()
        self.client.force_authenticate(user=user)

        response = self.client.post(
            '/api/file/upload',
            {'type': 'cover-art', 'filename': 'my-cool-album-cover.jpeg'},
            format='json',
        )

        data = response.json()
        self.assertEqual(
            data['url'], 'http://s3-dev.amuse.io:9000/amuse-cover-art-uploaded-dev'
        )
        self.assertTrue('fields' in data)
        self.assertEqual(data['fields']['Content-Type'], 'image/jpeg')

    def test_presigned_post_for_cover_art_png(self):
        user = UserFactory()
        self.client.force_authenticate(user=user)

        response = self.client.post(
            '/api/file/upload',
            {'type': 'cover-art', 'filename': 'my-cool-album-cover.png'},
            format='json',
        )

        data = response.json()
        self.assertEqual(
            data['url'], 'http://s3-dev.amuse.io:9000/amuse-cover-art-uploaded-dev'
        )
        self.assertTrue('fields' in data)
        self.assertEqual(data['fields']['Content-Type'], 'image/png')

    def test_presigned_post_for_audio_flac(self):
        user = UserFactory()
        self.client.force_authenticate(user=user)

        response = self.client.post(
            '/api/file/upload',
            {'type': 'audio-file', 'filename': 'best-song.flac'},
            format='json',
        )

        data = response.json()
        self.assertEqual(
            data['url'], 'http://s3-dev.amuse.io:9000/amuse-song-file-uploaded-dev'
        )
        self.assertTrue('fields' in data)
        self.assertNotIn('Content-Type', data['fields'].keys())

    def test_presigned_post_for_audio_wav(self):
        user = UserFactory()
        self.client.force_authenticate(user=user)

        response = self.client.post(
            '/api/file/upload',
            {'type': 'audio-file', 'filename': 'best-song.wav'},
            format='json',
        )

        data = response.json()
        self.assertEqual(
            data['url'], 'http://s3-dev.amuse.io:9000/amuse-song-file-uploaded-dev'
        )
        self.assertTrue('fields' in data)
        self.assertEqual(data['fields']['Content-Type'], 'audio/x-wav')

    def test_create_s3_client_from_storage(self):
        with self.settings(AWS_S3_HOST='s3-dev.amuse.io'):
            storage = mock.MagicMock()
            storage.access_key = 'w128rh0'
            storage.secret_key = 'blarg123'
            storage.endpoint_url = 'https://tjo:12412/'
            storage.use_ssl = True
            client = create_s3_client_from_storage(storage)
            self.assertEqual(client.meta.endpoint_url, f'https://tjo:12412/')

    def test_create_s3_client_default(self):
        with self.settings(AWS_S3_HOST='s3.amazonaws.com'):
            storage = mock.MagicMock()
            storage.access_key = 'w128rh0'
            storage.secret_key = 'blarg123'
            storage.endpoint_url = None
            client = create_s3_client_from_storage(storage)

            default_endpoint = 'https://s3.amazonaws.com'
            self.assertEqual(client.meta.endpoint_url, default_endpoint)
