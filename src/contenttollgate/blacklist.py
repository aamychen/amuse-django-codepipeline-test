from amuse import blacklist
from releases.models import SongArtistRole


def find_offending_words(release):
    ROLES = {
        'PRIMARY': SongArtistRole.ROLE_PRIMARY_ARTIST,
        'FEATURED': SongArtistRole.ROLE_FEATURED_ARTIST,
        'PRODUCER': SongArtistRole.ROLE_PRODUCER,
        'REMIXER': SongArtistRole.ROLE_REMIXER,
    }

    potential_matches = set()
    # Release can only have PRIMARY & FEATURED Role
    # so no need to go into ReleaseArtistRole here.
    for artist in release.artists.all():
        potential_matches.add(artist.name)

    for song in release.songs.all():
        subjects = song.songartistrole_set.filter(role__in=ROLES.values()).distinct()
        for subject in subjects:
            potential_matches.add(subject.artist.name)

    matches = []
    for potential in potential_matches:
        match = blacklist.find(potential)
        if match:
            matches.append((potential, match))
    return matches


def find_offending_artist_names(artist_names):
    matches = []
    for artist_name in artist_names:
        match = blacklist.find(artist_name)
        if match:
            matches.append((artist_name, match))
    return matches


def find_offending_artists(artists):
    return find_offending_artist_names([artist.name for artist in artists])
