from rest_framework import serializers
from releases.models import BlacklistedArtistName


class BlacklistedArtistNameSerializer(serializers.ModelSerializer):
    class Meta:
        model = BlacklistedArtistName
        fields = ('name',)
