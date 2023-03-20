import re

from rest_framework.exceptions import PermissionDenied

from amuse.events import created
from releases.models import Release, Song, SongArtistRole, Store
from users.models import ArtistV2, User


def save_release(release: Release):
    """
    Finalize Release model after modified by API.
    """

    # Priority users can use any genre for YouTube Content Id.
    if release.user.category is not User.CATEGORY_PRIORITY:
        exclude_youtube_content_id_for_disallowed_genres(release)

    enforce_release_version(release)
    release.genre = release.get_most_occuring_genre()

    release.save()


def get_or_create_artistv2_from_name(name, history_contributors, **artist_data):
    sanitized = re.sub(' +', ' ', name).strip()
    for artist in history_contributors:
        if artist.name == sanitized:
            return artist
    new_artist = ArtistV2.objects.create(name=sanitized, **artist_data)
    return new_artist


def enforce_release_version(release: Release):
    version = release.songs.first().version

    if release.songs.count() == 1:
        release.release_version = version
    else:
        for song in release.songs.all():
            if song.version != version:
                return
        release.release_version = Release.RELEASE_VERSIONS.get(version, version)


def exclude_youtube_content_id_for_disallowed_genres(release: Release):
    """
    Youtube content id should not be allowed for certain genres.
    """
    bad_genre_found = False
    for song in release.songs.all():
        if not song.genre.is_genre_qualified_for_youtube_content_id():
            song.youtube_content_id = Song.YT_CONTENT_ID_NONE
            song.save()
            bad_genre_found = True

    if bad_genre_found:
        release.stores.remove(Store.get_yt_content_id_store())


def verify_user(user: User):
    if not user.email_verified:
        raise PermissionDenied(
            'Release cannot be created as long as email is not verified'
        )


def event_created(request, release):
    created(request, release)


def get_contributors_from_history(user):
    all_releases_contributos = set(ArtistV2.objects.filter(owner=user).all())
    sar = SongArtistRole.objects.filter(song__release__user=user).select_related(
        'artist'
    )
    for row in sar:
        all_releases_contributos.add(row.artist)

    return all_releases_contributos


def get_contributor_from_cache(name, artistsv2_set):
    sanitized = re.sub(' +', ' ', name).strip()
    for artist in artistsv2_set:
        if artist.name == sanitized:
            return artist


def get_writers_from_history(user):
    writers = SongArtistRole.objects.filter(
        song__release__user=user, role=SongArtistRole.ROLE_WRITER
    ).select_related('artist')

    all_releases_writers = set()
    for row in writers:
        all_releases_writers.add(row.artist)

    return all_releases_writers


class VerifyPendingReleasesCount(object):
    @staticmethod
    def verify(user):
        count = pending_releases_count = Release.objects.filter(
            created_by=user, status=Release.STATUS_PENDING
        ).count()
        VerifyPendingReleasesCount._verify_for_free_user(user, count)
        VerifyPendingReleasesCount._verify_for_free_trial_user(user, count)

    @staticmethod
    def _verify_for_free_user(user, pending_releases_count):
        if user.tier == user.TIER_FREE:
            if pending_releases_count >= 1:
                raise PermissionDenied('Free user can only have one PENDING release')

    @staticmethod
    def _verify_for_free_trial_user(user, pending_releases_count):
        if user.is_free_trial_active():
            if pending_releases_count >= 1:
                raise PermissionDenied(
                    'Free Trial user can only have one PENDING release'
                )
