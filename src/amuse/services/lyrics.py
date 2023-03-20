from django.conf import settings
from amuse.vendor.aws import sqs
from releases.models import LyricsAnalysisResult


def analyze(song_id, filename, language, explicit):
    if language != "en" or explicit == 'explicit':
        return False

    message = {
        "id": song_id,
        "bucket": settings.AWS_SONG_FILE_UPLOADED_BUCKET_NAME,
        "path": "",
        "filename": filename,
        "language": "en-US",
    }
    return sqs.send_message(settings.LYRICS_SERVICE_REQUEST_QUEUE, message)


def callback(message):
    LyricsAnalysisResult.objects.update_or_create(
        song_id=message["id"],
        defaults=dict(explicit=message["explicit"], text=message["text"]),
    )
