from django.conf import settings
from boto3.session import Session


class Transcoder(object):
    def __init__(
        self, pipeline_id, region=None, access_key_id=None, secret_access_key=None
    ):
        self.pipeline_id = pipeline_id

        if not region:
            region = getattr(settings, 'AWS_REGION', None)
        self.aws_region = region

        if not access_key_id:
            access_key_id = getattr(settings, 'AWS_ACCESS_KEY_ID', None)
        self.aws_access_key_id = access_key_id

        if not secret_access_key:
            secret_access_key = getattr(settings, 'AWS_SECRET_ACCESS_KEY', None)
        self.aws_secret_access_key = secret_access_key

        assert self.aws_region is not None, 'Please provide AWS_REGION'
        assert self.aws_access_key_id is not None, 'Please provide AWS_ACCESS_KEY_ID'
        assert (
            self.aws_secret_access_key is not None
        ), 'Please provide AWS_SECRET_ACCESS_KEY'

        boto_session = Session(
            aws_access_key_id=self.aws_access_key_id,
            aws_secret_access_key=self.aws_secret_access_key,
            region_name=self.aws_region,
        )
        self.client = boto_session.client('elastictranscoder')

    def encode(self, input, outputs, **kwargs):
        self.message = self.client.create_job(
            PipelineId=self.pipeline_id, Input=input, Outputs=outputs, **kwargs
        )
        return self.message['Job']['Id']
