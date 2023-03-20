import mimetypes
from uuid import uuid4

import boto3
from django.conf import settings
from rest_framework.response import Response
from rest_framework.views import APIView

from amuse.mixins import LogMixin
from amuse.storages import S3Storage


def create_s3_client_from_storage(storage):
    session = boto3.session.Session()
    client = session.client(
        service_name='s3',
        aws_access_key_id=storage.access_key,
        aws_secret_access_key=storage.secret_key,
        endpoint_url=storage.endpoint_url,
    )

    return client


class FileUploadView(LogMixin, APIView):
    def post(self, request):
        file_type = request.data.get('type', None)
        filename = request.data.get('filename', None)

        storage = None
        errors = []
        if file_type == 'audio-file':
            storage = S3Storage(bucket_name=settings.AWS_SONG_FILE_UPLOADED_BUCKET_NAME)
        elif file_type == 'cover-art':
            storage = S3Storage(bucket_name=settings.AWS_COVER_ART_UPLOADED_BUCKET_NAME)
        else:
            errors.append('Type must be set to either "audio-file" or "cover-art"')

        if not filename or len(filename.split('.')) < 2:
            errors.append('Filename with extension must be provided')

        if errors:
            response = {'errors': errors}
            return Response(response, status=400, content_type='application/json')

        file_extension = filename.split('.')[-1].lower()
        write_filename = f'{str(uuid4())}.{file_extension}'

        fields = {}
        conditions = None

        content_type, _ = mimetypes.guess_type(filename)

        if content_type:
            fields['Content-Type'] = content_type
            conditions = [['starts-with', '$Content-Type', '']]

        client = create_s3_client_from_storage(storage)

        url_data = client.generate_presigned_post(
            Bucket=storage.bucket.name,
            Key=write_filename,
            Fields=fields,
            Conditions=conditions,
        )

        return Response(url_data, status=201, content_type='application/json')
