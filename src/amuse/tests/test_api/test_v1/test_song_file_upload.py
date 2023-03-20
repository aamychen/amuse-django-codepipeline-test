from unittest import mock

import responses
from django.urls import reverse_lazy as reverse
from rest_framework import status

from releases.downloads import GoogleDriveSongFileDownload
from releases.models import SongFileUpload
from releases.tests.factories import NewSongFileUploadFactory
from users.tests.factories import UserFactory

from ..base import AmuseAPITestCase


class SongFileUploadBaseTests:
    def test_create(self):
        response = self.client.post(self.list_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

        with self._file_url() as (_, _, file_url):
            user = UserFactory()
            self.client.force_authenticate(user=user)
            data = {'link': file_url}  # Used by link download - S3 upload
            response = self.client.post(self.list_url, data)

        response_data = response.json()
        upload = SongFileUpload.objects.get(id=response_data['id'])
        self.assertIsNotNone(upload.filename)
        self.assertEqual(upload.status, SongFileUpload.STATUS_COMPLETED)


class SongFileUploadAPITestCase(AmuseAPITestCase, SongFileUploadBaseTests):
    list_url = reverse('songfileupload-list')

    def test_update(self):
        sfu = NewSongFileUploadFactory(song=None)
        url = reverse('songfileupload-detail', args=(sfu.id,))
        response = self.client.patch(url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

        self.client.force_authenticate(user=sfu.user)
        data = {'filename': 'gorillaz.mp3'}
        response = self.client.patch(url, data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        data = {'file': 'gorillaz.mp3'}
        response = self.client.patch(url, data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        response_data = response.json()
        sfu = SongFileUpload.objects.get(id=response_data['id'])
        self.assertEqual(sfu.filename, response_data['filename'])
        self.assertEqual(sfu.status, SongFileUpload.STATUS_COMPLETED)


class LinkSongFileDownloadAPITestCase(AmuseAPITestCase, SongFileUploadBaseTests):
    list_url = reverse('releases-link-song-file-download-list')


class GoogleDriveSongFileDownloadAPITestCase(AmuseAPITestCase):
    @responses.activate
    @mock.patch('oauth2client.client.credentials_from_code', autospec=True)
    def test_create(self, _credentials_from_code):
        url = reverse('releases-google-drive-song-file-download-list')
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

        # Mock oauth2 access token
        _credentials_from_code.return_value.get_access_token.return_value.access_token = (
            'foobar'
        )

        # Keep original below mocked
        get_download_link = GoogleDriveSongFileDownload.get_download_link

        def _get_download_link(zelph):
            # Run original method to get real link
            link = get_download_link(zelph)

            # Mock link download response for real link
            with self._file() as (_, f):
                responses.add(responses.GET, link, body=f.read(), status=200)

            return link

        # Mock google get_download_link, see above
        m = 'releases.downloads.GoogleDriveSongFileDownload.get_download_link'
        with mock.patch(m, _get_download_link):
            user = UserFactory()
            self.client.force_authenticate(user=user)
            data = {
                'auth_code': 'my-auth-code',
                'file_id': 'my-file-id',
                'filename': 'gorillaz.mp3',
            }
            response = self.client.post(url, data)

        response_data = response.json()
        upload = SongFileUpload.objects.get(id=response_data['id'])
        self.assertIsNotNone(upload.filename)
        self.assertEqual(upload.status, SongFileUpload.STATUS_COMPLETED)
