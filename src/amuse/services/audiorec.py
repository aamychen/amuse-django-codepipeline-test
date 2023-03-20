import logging
from django.conf import settings
from amuse.models.acrcloud import ACRCloudMatch
from amuse.vendor.aws import sqs
from releases.models.song import Song

MIN_SCORE = 94

logger = logging.getLogger(__name__)


def recognize(song_id, filename):
    message = {
        "id": song_id,
        "bucket": settings.AWS_SONG_FILE_UPLOADED_BUCKET_NAME,
        "path": "",
        "filename": filename,
    }
    return sqs.send_message(settings.AUDIO_RECOGNITION_SERVICE_REQUEST_QUEUE, message)


def callback(message):
    song = Song.objects.get(pk=message["id"])
    if message["errors"]:
        logger.warning(f"Audio recognition errors: {message['errors']}")
    elif message["results"]:
        for result in message["results"]:
            if result["score"] <= MIN_SCORE:
                continue
            ACRCloudMatch.objects.create(
                song=song,
                score=result["score"],
                offset=result["offset"],
                artist_name=result["artist_name"],
                album_title=result["album_title"],
                track_title=result["track_title"],
                match_upc=result["match_upc"],
                match_isrc=result["match_isrc"],
                external_metadata=result["external_metadata"],
            )
