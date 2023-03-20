import pytest

from amuse.api.v4.serializers.blacklisted_artist_name import (
    BlacklistedArtistNameSerializer,
)
from releases.models import BlacklistedArtistName


@pytest.mark.django_db
def test_to_representation_method_returns_blacklisted_artist_name():
    artist_name = 'Coldplay'
    blacklisted_artist_name = BlacklistedArtistName.objects.create(name=artist_name)
    serializer = BlacklistedArtistNameSerializer()
    assert serializer.to_representation(blacklisted_artist_name)['name'] == artist_name
