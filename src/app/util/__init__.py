import requests
from contextlib import closing
from django.conf import settings
from storages.backends.s3boto3 import S3Boto3StorageFile
from uuid import uuid4

from amuse.storages import S3Storage


def is_profile_photo_s3_url(url):
    return settings.AWS_PROFILE_PHOTO_BUCKET_NAME in url


def migrate_user_profile_photo_to_s3(from_url):
    storage = S3Storage(
        bucket_name=settings.AWS_PROFILE_PHOTO_BUCKET_NAME, querystring_auth=False
    )
    filename = '%s.jpg' % str(uuid4()).upper()

    with closing(requests.get(from_url, stream=True, timeout=(5, 180))) as r:
        if r.status_code // 100 != 2:
            return None

        with S3Boto3StorageFile(name=filename, mode='w', storage=storage) as s3file:
            for chunk in r.iter_content(None):
                if not chunk:
                    break
                s3file.write(chunk)

    return storage.url(filename)


def user_profile_photo_s3_url(key):
    storage = S3Storage(
        bucket_name=settings.AWS_PROFILE_PHOTO_BUCKET_NAME, querystring_auth=False
    )

    if not key or not storage.exists(key):
        return None

    return storage.url(key)
