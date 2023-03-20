from rest_framework import serializers
from releases.models import CoverArt


class CoverArtSerializer(serializers.ModelSerializer):
    thumbnail = serializers.URLField(source='thumbnail_url_400', read_only=True)
    filename = serializers.CharField(source='file', read_only=True)

    class Meta:
        model = CoverArt
        fields = ('id', 'file', 'filename', 'thumbnail', 'checksum')
