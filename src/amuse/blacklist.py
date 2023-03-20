from amuse.vendor.spotify.artist_blacklist.blacklist import fuzzify
from releases.models.blacklisted_artist_name import BlacklistedArtistName


def find(text):
    fuzzified_text = fuzzify(text)
    queryset = BlacklistedArtistName.objects.filter(fuzzy_name=fuzzified_text)
    if queryset.count() >= 1:
        blacklisted_artist_name = queryset.first()
        return blacklisted_artist_name.name
    else:
        return None
