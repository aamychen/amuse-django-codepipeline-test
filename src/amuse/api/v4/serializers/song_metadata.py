from rest_framework import serializers

from amuse.serializers import StringMapField
from releases.models import Song


class SongMetadataSerializer(serializers.ModelSerializer):
    explicit = StringMapField(mapping=Song.EXPLICIT_CHOICES)
    primary_artists = serializers.SerializerMethodField()

    def get_primary_artists(self, song):
        return ', '.join([artist.name for artist in song.get_primary_artists()])

    class Meta:
        model = Song
        fields = ('id', 'explicit', 'name', 'primary_artists')
