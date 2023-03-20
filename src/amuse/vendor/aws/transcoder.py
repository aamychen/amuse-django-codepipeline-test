from os.path import splitext
from boto3.session import Session
from django.conf import settings


def transcode(filename):
    transcoder = Transcoder()
    transcoder.transcode(filename)


class Transcoder:
    def __init__(self):
        session = Session(
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            region_name=settings.AWS_REGION,
        )
        self._client = session.client('elastictranscoder')
        self.job_id = None

    def transcode(self, filename):
        response = self._client.create_job(
            PipelineId=settings.AWS_SONG_FILE_TRANSCODER_PIPELINE,
            Input={'Key': filename},
            Outputs=[
                {
                    'PresetId': settings.AWS_FLAC_PRESET_ID,
                    'Key': 'et-%s.flac' % splitext(filename)[0],
                },
                {
                    'PresetId': settings.AWS_MP3128K_PRESET_ID,
                    'Key': 'et-%s.mp3' % splitext(filename)[0],
                },
            ],
        )
        self.job_id = response['Job']['Id']
