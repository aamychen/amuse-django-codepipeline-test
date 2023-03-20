import os
import tempfile
from pathlib import Path
from uuid import uuid4
from django.conf import settings
from amuse.vendor.aws import s3


def test_create_resource():
    resource = s3.create_resource()
    resource.meta.client.head_bucket(Bucket=settings.AWS_STORAGE_BUCKET_NAME)


def test_sync_dir():
    resource = s3.create_resource()
    client = resource.meta.client
    key = f'{str(uuid4())}/{str(uuid4())}/{str(uuid4())}.test'
    res = client.put_object(
        Bucket=settings.AWS_STORAGE_BUCKET_NAME, Key=key, Body=b'body'
    )
    s3.sync_dir(
        settings.AWS_STORAGE_BUCKET_NAME, key.split(os.sep)[0], '/tmp/', resource
    )
    assert os.path.exists('/tmp/' + key.rsplit(key.split(os.sep)[0])[1])


def test_upload_dir():
    bucket_name = str(uuid4())
    remote_dir = str(uuid4())
    resource = s3.create_resource()
    resource.meta.client.create_bucket(Bucket=bucket_name)

    with tempfile.TemporaryDirectory() as d:
        dir01 = Path(str(uuid4()))
        file01 = dir01 / Path("test.01")

        dir02 = Path(str(uuid4())) / Path(str(uuid4()))
        file02 = dir02 / Path("test.02")

        dir03 = Path(str(uuid4())) / Path(str(uuid4())) / Path(str(uuid4()))
        file03 = dir03 / Path("test.03")

        (Path(d) / dir01).mkdir(parents=True)
        (Path(d) / dir02).mkdir(parents=True)
        (Path(d) / dir03).mkdir(parents=True)

        (Path(d) / file01).touch()
        (Path(d) / file02).touch()
        (Path(d) / file03).touch()

        s3.upload_dir(d, bucket_name, remote_dir)

        resource.meta.client.head_object(
            Bucket=bucket_name, Key=f"{remote_dir}/{file01}"
        )
        resource.meta.client.head_object(
            Bucket=bucket_name, Key=f"{remote_dir}/{file02}"
        )
        resource.meta.client.head_object(
            Bucket=bucket_name, Key=f"{remote_dir}/{file03}"
        )


def test_create_s3_uri():
    assert s3.create_s3_uri("foo", "bar.json") == "s3://foo/bar.json"


def test_create_presigned_url():
    signed_url = s3.create_presigned_url(
        bucket_name=settings.AWS_BATCH_DELIVERY_BUCKET_NAME, object_name="test.xml"
    )

    assert settings.AWS_BATCH_DELIVERY_BUCKET_NAME in signed_url
    assert "test.xml" in signed_url
    assert "&Signature=" in signed_url
    assert "&Expires=" in signed_url
