import logging
from collections import defaultdict

import pytest
from _pytest.monkeypatch import MonkeyPatch
from django.conf import settings
from bananas.environment import env

from amuse.storages import S3Storage

logger = logging.getLogger()

import logging
import boto3
from botocore.exceptions import ClientError


def bucket_exist(s3_client, bucket_name):
    try:
        s3_client.head_bucket(Bucket=bucket_name)
        return True
    except ClientError as error:
        if error.response['ResponseMetadata']['HTTPStatusCode'] == 404:
            return False


def create_bucket(bucket_name):
    """Create an S3 bucket in a specified region

    If a region is not specified, the bucket is created in the S3 default
    region (us-east-1).

    :param bucket_name: Bucket to create
    :param region: String region to create bucket in, e.g., 'us-west-2'
    :return: True if bucket created, else False
    """

    # Create bucket
    try:
        s3_client = boto3.client(
            's3',
            region_name=settings.AWS_S3_REGION_NAME,
            endpoint_url=settings.AWS_S3_ENDPOINT_URL,
        )
        location = {
            'LocationConstraint': settings.AWS_S3_REGION_NAME,
        }
        if not bucket_exist(s3_client, bucket_name):
            s3_client.create_bucket(
                Bucket=bucket_name, CreateBucketConfiguration=location
            )
            return True
        return False
    except ClientError as e:
        logging.error(e)
        return False


@pytest.fixture(scope='session', autouse=True)
def bucket_configuration():
    buckets = []
    buckets.append(env.get('AWS_STORAGE_BUCKET_NAME'))
    buckets.append(env.get('AWS_COVER_ART_UPLOADED_BUCKET_NAME'))
    buckets.append(env.get('AWS_SONG_FILE_UPLOADED_BUCKET_NAME'))
    buckets.append(env.get('AWS_SONG_FILE_TRANSCODED_BUCKET_NAME'))
    buckets.append(env.get('AWS_TRANSACTION_FILE_BUCKET_NAME'))
    buckets.append(env.get('AWS_PROFILE_PHOTO_BUCKET_NAME'))
    buckets.append(env.get('AWS_BULK_DELIVERY_JOB_BUCKET_NAME'))
    buckets.append(env.get('AWS_BATCH_DELIVERY_BUCKET_NAME'))
    buckets.append(env.get('AWS_BATCH_DELIVERY_FILE_BUCKET_NAME'))
    buckets.append(env.get('AWS_SONG_FILE_TRANSCODED_BUCKET_NAME'))

    for bucket_name in buckets:
        if bucket_name is not None:
            create_bucket(bucket_name)


@pytest.fixture(scope='session', autouse=True)
def celery_configuration():
    settings.CELERY_ALWAYS_EAGER = True


@pytest.fixture(scope='session', autouse=True)
def fast_password_hashing():
    settings.PASSWORD_HASHERS = ['django.contrib.auth.hashers.MD5PasswordHasher']


@pytest.fixture(scope="session", autouse=True)
def block_unmocked_requests():
    """
    Prevents requests from being made unless they are mocked.
    Helps avoid inadvertent dependencies on external resources during the test run.
    """

    def mocked_send(*args, **kwargs):
        prepared_request = args[1]

        logger.warning(
            'Unmocked %s request was blocked to %s',
            prepared_request.method,
            prepared_request.url,
        )

        raise RuntimeError('Tests must mock all HTTP requests!')

    # The standard monkeypatch fixture cannot be used with session scope:
    # https://github.com/pytest-dev/pytest/issues/363
    monkeypatch = MonkeyPatch()
    # Monkeypatching here since any higher level would break responses:
    # https://github.com/getsentry/responses/blob/0.5.1/responses.py#L295
    monkeypatch.setattr('requests.adapters.HTTPAdapter.send', mocked_send)

    yield monkeypatch

    monkeypatch.undo()


@pytest.fixture(scope="session", autouse=True)
def song_file_uploaded():
    storage = S3Storage(bucket_name=settings.AWS_SONG_FILE_UPLOADED_BUCKET_NAME)
    with storage.open("wave.wav", "w") as f:
        f.write(open('amuse/tests/test_api/data/wave.wav', 'rb').read())


@pytest.fixture(scope="session", autouse=True)
def coverart_file():
    storage = S3Storage(bucket_name=settings.AWS_COVER_ART_UPLOADED_BUCKET_NAME)
    with storage.open("cover.jpg", "w") as f:
        f.write(open('amuse/tests/test_api/data/amuse.jpg', 'rb').read())
