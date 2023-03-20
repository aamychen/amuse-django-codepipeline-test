import os
import boto3
from django.conf import settings


def create_resource(
    access_key_id=settings.AWS_ACCESS_KEY_ID,
    secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
):
    endpoint = None
    protocol = 'https'
    if getattr(settings, 'AWS_S3_HOST', None) == 's3-dev.amuse.io':
        protocol = 'http'
        endpoint = f'{protocol}://{settings.AWS_S3_HOST}:{settings.AWS_S3_PORT}/'
    return boto3.resource(
        service_name='s3',
        aws_access_key_id=access_key_id,
        aws_secret_access_key=secret_access_key,
        endpoint_url=endpoint,
    )


def sync_dir(bucket, remote_dir, local_dir, resource=None, prefix_strip=''):
    resource = resource or create_resource()
    paginator = resource.meta.client.get_paginator('list_objects')
    for result in paginator.paginate(Bucket=bucket, Delimiter='/', Prefix=remote_dir):
        if result.get('CommonPrefixes'):
            for subdir in result.get('CommonPrefixes'):
                sync_dir(
                    bucket,
                    subdir.get('Prefix'),
                    local_dir,
                    resource,
                    prefix_strip or remote_dir,
                )
        if result.get('Contents'):
            for file in result.get('Contents'):
                local_filename = (
                    local_dir + os.sep + file.get('Key').rsplit(prefix_strip)[1]
                )
                if not os.path.exists(os.path.dirname(local_filename)):
                    os.makedirs(os.path.dirname(local_filename))
                resource.meta.client.download_file(
                    bucket, file.get('Key'), local_filename
                )


def download_file(bucket, remote_file, local_file):
    create_resource().Bucket(bucket).download_file(remote_file, local_file)


def upload_dir(local_dir, bucket, remote_dir="", resource=None):
    resource = resource or create_resource()
    for dirpath, dirnames, filenames in os.walk(local_dir):
        for filename in filenames:
            local_filename = f"{dirpath}/{filename}"
            remote_filename = local_filename.rsplit(local_dir)[1]
            resource.meta.client.upload_file(
                local_filename, bucket, f"{remote_dir}{remote_filename}"
            )


def create_s3_uri(bucket, key):
    return f"s3://{bucket}/{key}"


def create_presigned_url(bucket_name, object_name, expiration=3600):
    s3_client = boto3.client("s3")
    return s3_client.generate_presigned_url(
        "get_object",
        Params={"Bucket": bucket_name, "Key": object_name},
        ExpiresIn=expiration,
    )
