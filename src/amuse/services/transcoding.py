import json
import logging
from os.path import splitext
from django.conf import settings
from amuse.vendor.aws.transcoder import Transcoder
from amuse.models import Transcoding
from releases.models import SongFile, release_completed
from waffle import switch_is_active
from amuse.vendor.aws.sqs import create_client as create_sqs_client

logger = logging.getLogger(__name__)

PRESETS = {
    settings.AWS_FLAC_PRESET_ID: SongFile.TYPE_FLAC,
    settings.AWS_MP3128K_PRESET_ID: SongFile.TYPE_MP3,
}


def transcode(song, audio_filename):
    transcoding = Transcoding.objects.create(
        song=song, transcoder_name=Transcoding.AUDIO_TRANSCODER_SERVICE
    )

    transcode_audio_transcoder_service(
        create_sqs_client(), transcoding.id, audio_filename
    )


def callback(message):
    main_transcoder = (
        'audio-transcoder-service'
        if switch_is_active('service:audio-transcoder:enabled')
        else 'elastic'
    )

    if 'jobId' in message:
        transcoding = Transcoding.objects.filter(
            transcoder_job=message['jobId']
        ).first()
        if not transcoding:
            logger.error(
                'Found not transcoding object with id \'%s\'' % message['jobId']
            )
            return
        transcoding.status = Transcoding.internal_status(message['state'])
        transcoding.errors = [
            o.get('statusDetail')
            for o in message.get('outputs', [])
            if o.get('statusDetail', None)
        ]
        transcoding.save()

        if main_transcoder == 'elastic':
            if transcoding.status == Transcoding.STATUS_COMPLETED:
                for output in message['outputs']:
                    sf, created = SongFile.objects.get_or_create(
                        song=transcoding.song,
                        type=PRESETS[output['presetId']],
                        defaults={
                            "duration": 0
                        },  # duration is non-nullable without a default
                    )
                    sf.duration = output["duration"]
                    sf.file = output["key"]
                    sf.checksum = None  # trigger a new checksum calc
                    sf.save()

                    if created:
                        release_completed(transcoding.song.release)

    if 'id' in message:
        transcoding = Transcoding.objects.filter(id=message['id']).first()
        if not transcoding:
            logger.error('Found not transcoding object with id \'%s\'' % message['id'])
            return

        if message["status"] == 'success':
            transcoding.status = Transcoding.STATUS_COMPLETED
        elif message["status"] == 'error':
            transcoding.status = Transcoding.STATUS_ERROR

        if message["errors"] == None:
            transcoding.errors = []
        else:
            transcoding.errors = [message["errors"]]

        transcoding.save()

        if main_transcoder == 'audio-transcoder-service':
            if transcoding.status == Transcoding.STATUS_COMPLETED:
                for output in message['outputs']:
                    if output["format"] == 'flac':
                        format_preset = SongFile.TYPE_FLAC
                    elif output["format"] == 'mp3':
                        format_preset = SongFile.TYPE_MP3

                    sf, created = SongFile.objects.get_or_create(
                        song=transcoding.song,
                        type=format_preset,
                        defaults={
                            "duration": 0
                        },  # duration is non-nullable without a default
                    )
                    sf.duration = output["duration"]
                    sf.file = output["key"]
                    sf.checksum = None  # trigger a new checksum calc
                    sf.save()

                    if created:
                        release_completed(transcoding.song.release)


def build_message(id, filename):
    message = {
        "id": str(id),
        "input": {
            "key": filename,
            "bucket": settings.AWS_SONG_FILE_UPLOADED_BUCKET_NAME,
        },
        "outputs": [
            {
                "key": f"{splitext(filename)[0]}.flac",
                "format": "flac",
                "bucket": settings.AWS_SONG_FILE_TRANSCODED_BUCKET_NAME,
            },
            {
                "key": f"{splitext(filename)[0]}.mp3",
                "format": "mp3",
                "bucket": settings.AWS_SONG_FILE_TRANSCODED_BUCKET_NAME,
            },
        ],
    }
    return message


def transcode_audio_transcoder_service(client, id, audio_filename):
    message = build_message(id, audio_filename)
    message_string = json.dumps(message)

    response = client.get_queue_url(
        QueueName=settings.AUDIO_TRANSCODER_SERVICE_REQUEST_QUEUE_NAME
    )

    client.send_message(QueueUrl=response["QueueUrl"], MessageBody=message_string)
