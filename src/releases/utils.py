import logging
from datetime import datetime, timedelta

from celery import chain
from django.conf import settings
from django.db.models import Q

from amuse import tasks
from releases.models import Song, SongArtistRole, SongFile, Release, Store


logger = logging.getLogger(__name__)


RELEASE_ALLOWED_FLAGS = [0, 128, 524288, 524416]
SONG_ALLOWED_FLAGS = [0, 16]


def split_genres(genre):
    main = sub = None
    if genre.parent is not None:
        main = genre.parent
        sub = genre
    else:
        main = genre
    return main, sub


def release_explicit(release):
    return (
        'explicit'
        if any(s.explicit == Song.EXPLICIT_TRUE for s in release.songs.all())
        else 'none'
    )


def default_original_release_date(release):
    if release.original_release_date:
        return release.original_release_date
    elif release.release_date:
        return release.release_date
    else:
        return release.created


def default_label_name(release):
    return release.label if release.label else release.main_primary_artist.name


def filter_song_file_flac(song):
    return song.files.filter(type=SongFile.TYPE_FLAC).first()


def filter_song_file_mp3(song):
    return song.files.filter(type=SongFile.TYPE_MP3).first()


def get_contributors_from_history(user):
    all_releases_contributos = []
    sar = SongArtistRole.objects.filter(song__release__user=user).distinct()
    for row in sar:
        all_releases_contributos.append(
            {
                'id': row.artist.id,
                'name': row.artist.name,
                'spotify_id': row.artist.spotify_id,
            }
        )

    return dict((v['name'], v) for v in all_releases_contributos).values()


def queue_celery_tasks(
    song_id,
    audio_s3_key,
    audio_dropbox_link,
    google_drive_auth_code,
    google_drive_file_id,
    filename_extension,
):
    if audio_s3_key:
        # No need to run task async as transcoding is done async anyway
        tasks.audio_recognition(audio_s3_key, song_id)
        tasks.analyze_lyrics(audio_s3_key, song_id)
        tasks.transcode(audio_s3_key, song_id)
    elif audio_dropbox_link:
        chain(
            tasks.download_to_bucket.s(
                audio_dropbox_link,
                settings.AWS_SONG_FILE_UPLOADED_BUCKET_NAME,
                target_extension=filename_extension,
            ),
            tasks.analyze_lyrics.s(song_id),
            tasks.audio_recognition.s(song_id),
            tasks.transcode.s(song_id),
        ).delay()
    elif google_drive_auth_code and google_drive_file_id:
        chain(
            tasks.google_drive_to_bucket.s(
                google_drive_auth_code,
                google_drive_file_id,
                settings.AWS_SONG_FILE_UPLOADED_BUCKET_NAME,
                target_extension=filename_extension,
            ),
            tasks.analyze_lyrics.s(song_id),
            tasks.audio_recognition.s(song_id),
            tasks.transcode.s(song_id),
        ).delay()


def parse_label(release: Release):
    if release.label and len(release.label) > 0:
        return release.label
    else:
        return release.main_primary_artist.name


def get_upcoming_releases(days_to_release: int = 5, has_link: bool = False):
    """
    Returns list of Releases are scheduled for release.

    :arg days_to_release: Indicates days until release timedelta.
    Releases that will be released in timespan of days_to_release or less days are returned.
    :arg has_link: Indicates does the release have link or not.
    If value is set to false then only Releases without link are returned.
    """
    releases = Release.objects.filter(
        release_date__gte=datetime.today(),
        release_date__lte=datetime.today() + timedelta(days=days_to_release),
        upc__isnull=False,
    )
    if not has_link:
        releases = releases.filter(Q(link=None) | Q(link=''))

    return releases


def ordered_stores_queryset(exclude_stores=None):
    return (
        Store.objects.filter(admin_active=True)
        .exclude(internal_name__in=exclude_stores or [])
        .order_by('-show_on_top', '-active', '-is_pro', 'name')
    )


def filter_release_error_flags(releases, job_id=None):
    return filter_error_flags(releases, RELEASE_ALLOWED_FLAGS, job_id)


def filter_songs_error_flags(songs, job_id=None):
    return filter_error_flags(songs, SONG_ALLOWED_FLAGS, job_id)


def filter_error_flags(objs, allowed_flags, job_id=None):
    assert objs.model in [Release, Song]

    cls_name = objs.model.__name__
    results = []

    for obj in objs:
        if obj.error_flags.mask in allowed_flags:
            results.append(obj)
        else:
            logger.warning(
                "%s %s %s flags %s not in %s"
                % (job_id, cls_name, obj.pk, obj.error_flags.mask, allowed_flags)
            )

    return results
