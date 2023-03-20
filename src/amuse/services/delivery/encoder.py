from collections import defaultdict

from django.conf import settings

from amuse.services.release_delivery_info import ReleaseDeliveryInfo
from amuse.tasks import _calculate_django_file_checksum
from amuse.vendor.aws import s3
from releases.models import SongArtistRole, FugaMetadata
from releases.models.fuga_metadata import FugaStore
from releases.utils import (
    default_label_name,
    default_original_release_date,
    filter_song_file_flac,
    release_explicit,
    split_genres,
)


def release_json(release, check_empty_checksum=True) -> dict:
    label_name = default_label_name(release)
    original_release_date = default_original_release_date(release)
    main_genre, sub_genre = split_genres(release.genre)
    checksum = _calculate_django_file_checksum(release.cover_art.file)
    is_fuga_release = FugaMetadata.objects.filter(release=release).first()

    if checksum != release.cover_art.checksum:
        raise ValueError(
            "Delivery encoder release %s coverart checksum error. %s is not %s"
            % (release.id, checksum, release.cover_art.checksum)
        )

    return {
        'artists': release_artists_json(release),
        'artwork': {
            'file': s3.create_s3_uri(
                settings.AWS_COVER_ART_UPLOADED_BUCKET_NAME, release.cover_art.file.name
            ),
            'md5': release.cover_art.checksum,
            'proprietary_id': release.cover_art.pk,
            'size': release.cover_art.file.size,
        },
        'asset_labels': release_asset_labels_json(release),
        'cline_text': label_name,
        'cline_year': original_release_date.year,
        'display_artist_name': release.main_primary_artist.name,
        'explicit': release_explicit(release),
        'fuga_metadata': fuga_metadata_json(release) if is_fuga_release else {},
        'genre': genre_json(main_genre),
        'id': release.pk,
        'user_id': release.user.pk,
        'label': label_name,
        'meta_language': language_json(release.meta_language),
        'name': release.name,
        'original_release_date': original_release_date.isoformat(),
        'pline_text': label_name,
        'pline_year': original_release_date.year,
        'release_date': release.release_date.isoformat()
        if release.release_date
        else None,
        'subgenre': genre_json(sub_genre),
        'tracks': tracks_json(release, check_empty_checksum),
        'type': release.get_type_display(),
        'upc': release.upc_code,
        'version': release.release_version,
    }


def genre_json(genre) -> dict:
    if genre is None:
        return {}
    formatted_genre = {'name': genre.name}
    if genre.apple_code:
        formatted_genre['code'] = genre.apple_code
    return formatted_genre


def language_json(metadata_language) -> dict:
    if not metadata_language:
        return {}
    return {
        'fuga_code': metadata_language.fuga_code,
        'iso_code': metadata_language.iso_639_1,
        'iso_code2': metadata_language.iso_639_2,
    }


def release_artists_json(release) -> list:
    """
    Always put main primary artist first and include any artist that
    has contributed to all songs on the release.

    We generate a sequence dynamically as album level sequencing is not accounted
    for with SongArtistRole.artist_sequence.

    Not all of these artists are displayed on album level. DDEX for example only
    display artists that falls into the DisplayArtist category. This additional
    filtering is handled by the release-delivery service so is not something we need
    to worry about here.
    """
    contributors = []

    # Find artists that contribute to songs
    artist_contributions = defaultdict(set)
    song_contributors = defaultdict(list)
    songs = list(release.songs.all())
    song_count = len(songs)

    main_primary_artist = SongArtistRole.objects.filter(
        song__release_id=release.id,
        artist=release.main_primary_artist,
        role=SongArtistRole.ROLE_PRIMARY_ARTIST,
    ).first()

    contributors.append(
        {
            "id": main_primary_artist.artist.id,
            "name": main_primary_artist.artist.name,
            "role": main_primary_artist.get_role_display(),
            "sequence": 1,
            "spotify_id": main_primary_artist.artist.spotify_id,
            "audiomack_id": main_primary_artist.artist.audiomack_id,
            "apple_id": main_primary_artist.artist.apple_id,
        }
    )

    for song in songs:
        for role in (
            song.songartistrole_set.filter(
                role__in=[
                    SongArtistRole.ROLE_PRIMARY_ARTIST,
                    SongArtistRole.ROLE_FEATURED_ARTIST,
                    SongArtistRole.ROLE_REMIXER,
                ]
            )
            .exclude(artist=main_primary_artist.artist)
            .order_by("-role")
        ):
            artist_contributions[role.artist].add(song.pk)
            song_contributors[role.artist].append(role)

    i = 2
    # Add artists that contributed to every song at release-level
    additional_contributors = []
    for artist, songs_contributed_to in artist_contributions.items():
        if len(songs_contributed_to) == song_count:
            for song_artist_role in song_contributors[artist]:
                if not any(
                    filter(
                        lambda x: x['name'] == artist.name
                        and x['role'] == song_artist_role.get_role_display(),
                        additional_contributors,
                    )
                ):
                    additional_contributors.append(
                        {
                            "id": artist.id,
                            "name": artist.name,
                            "role": song_artist_role.get_role_display(),
                            "sequence": i,
                            "spotify_id": artist.spotify_id,
                            "audiomack_id": artist.audiomack_id,
                            "apple_id": artist.apple_id,
                        }
                    )
                    i += 1

    additional_contributors.sort(
        key=lambda c: (c['role'] != 'primary_artist', c['sequence'])
    )
    for i, additional_contributor in enumerate(additional_contributors, 2):
        additional_contributor['sequence'] = i
    return contributors + additional_contributors


def song_artists_json(song) -> list:
    """
    This builds on the business logic that a main_primary_artist is always a
    primary_artist with sequence 1 on all tracks.

    We make sure to not overwrite the sequences in the database so whatever is
    displayed in jarvi5 is sent over to the release-delivery service.

    DDEX/Fuga for example groups the artists into categories so that has a higher
    precedence than sequence when deciding display order in the release-delivery
    service.
    """
    contributors = []
    for song_artist_role in song.songartistrole_set.order_by('role', 'artist_sequence'):
        contributors.append(
            {
                "id": song_artist_role.artist.id,
                "name": song_artist_role.artist.name,
                "role": song_artist_role.get_role_display(),
                "sequence": song_artist_role.artist_sequence,
                "spotify_id": song_artist_role.artist.spotify_id,
                "audiomack_id": song_artist_role.artist.audiomack_id,
                "apple_id": song_artist_role.artist.apple_id,
            }
        )

    return contributors


def tracks_json(release, check_empty_checksum=True) -> list:
    tracks = []
    for song in release.songs.all().order_by('sequence'):
        flac_file = filter_song_file_flac(song)

        if check_empty_checksum and flac_file.checksum is None:
            raise ValueError(
                "Delivery encoder release %s song %s checksum is None error"
                % (release.id, song.id)
            )

        main_genre, sub_genre = split_genres(song.genre)
        tracks.append(
            {
                'artists': song_artists_json(song),
                'asset_labels': track_asset_labels_json(song),
                'audio': {
                    'file': s3.create_s3_uri(
                        settings.AWS_SONG_FILE_TRANSCODED_BUCKET_NAME,
                        flac_file.file.name,
                    ),
                    'size': flac_file.file.size,
                    'md5': flac_file.checksum,
                    'codec': flac_file.get_type_display(),
                },
                'id': song.pk,
                'duration': flac_file.duration,
                'explicit': song.get_explicit_display(),
                'genre': genre_json(main_genre),
                'isrc': song.isrc.code,
                'proprietary_id': '%s_%s' % (release.upc_code, song.isrc.code),
                'meta_audio_locale': language_json(song.meta_audio_locale),
                'meta_language': language_json(song.meta_language),
                'name': song.name,
                'preview_length': 30,
                'preview_start': song.preview_start_time or 0,
                'recording_year': song.recording_year,
                'sequence': song.sequence,
                'subgenre': genre_json(sub_genre),
                'version': song.version,
                'youtube_content_id': song.get_youtube_content_id_display(),
            }
        )
    return tracks


def release_asset_labels_json(release) -> list:
    labels = []
    release_asset_labels = release.asset_labels.values_list(
        "asset_label__name", flat=True
    )
    for label in release_asset_labels:
        labels.append(label)
    return labels


def track_asset_labels_json(song) -> list:
    labels = []
    song_asset_labels = song.asset_labels.values_list("asset_label__name", flat=True)
    for label in song_asset_labels:
        labels.append(label)
    return labels


def fuga_metadata_json(release):
    return {
        "facebook_is_ean": ReleaseDeliveryInfo.has_been_live_on_fuga_store(
            release.id, FugaStore.FACEBOOK.value
        ),
        "spotify_is_ean": ReleaseDeliveryInfo.has_been_live_on_fuga_store(
            release.id, FugaStore.SPOTIFY.value
        ),
    }
