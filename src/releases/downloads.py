import requests
from requests.exceptions import HTTPError
from contextlib import closing
from os.path import splitext
from uuid import uuid4
from urllib.parse import urlparse
from amuse.celery import app
from django.conf import settings
from oauth2client import client
from releases.models import SongFileUpload
from storages.backends.s3boto3 import S3Boto3StorageFile
from amuse.storages import S3Storage


class GoogleDriveSongFileDownload:
    SCOPE = 'https://www.googleapis.com/auth/drive.file'
    LINK_FORMAT = 'https://www.googleapis.com/drive/v3/files/%s?alt=media'

    def __init__(self, auth_code, file_id):
        self.auth_code = auth_code
        self.file_id = file_id
        self.access_token = None

    def get_access_token(self):
        if self.access_token is None:
            credentials = client.credentials_from_code(
                client_id=settings.GOOGLE_OAUTH2_CLIENT_ID,
                client_secret=settings.GOOGLE_OAUTH2_CLIENT_SECRET,
                scope=self.SCOPE,
                code=self.auth_code,
                redirect_uri=settings.GOOGLE_OAUTH2_REDIRECT_URI,
            )
            self.access_token = credentials.get_access_token().access_token
        return self.access_token

    def get_download_link(self):
        return self.LINK_FORMAT % self.file_id

    def get_headers(self):
        access_token = self.get_access_token()
        return {'Authorization': f'Bearer {access_token}'}


class LinkSongFileDownload:
    def __init__(self, link):
        self.link = link
        self.upload_id = None


def download_songfileupload_link(songfileupload_id):
    if not isinstance(songfileupload_id, int):
        return
    songfileupload = SongFileUpload.objects.get(pk=songfileupload_id)

    def parse_filename(link):
        parts = urlparse(link)
        if parts.path is not None and len(parts.path):
            link = parts.path
        return link.split('/')[-1]

    read_filename = parse_filename(songfileupload.link)
    write_filename = '%s%s' % (str(uuid4()), splitext(read_filename)[1])
    storage = S3Storage(bucket_name=settings.AWS_SONG_FILE_UPLOADED_BUCKET_NAME)
    with closing(requests.get(songfileupload.link, stream=True, timeout=(5, 180))) as r:
        if r.status_code // 100 != 2:
            raise HTTPError(
                'Song file link download failed with status code: %d, url: %s'
                % (r.status_code, songfileupload.link)
            )
        with S3Boto3StorageFile(
            name=write_filename, mode='w', storage=storage
        ) as s3file:
            for chunk in r.iter_content(None):
                if not chunk:
                    break
                s3file.write(chunk)
            songfileupload.filename = write_filename
            songfileupload.status = SongFileUpload.STATUS_COMPLETED
            songfileupload.save()
