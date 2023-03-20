from rest_framework import serializers

from releases.models import MetadataLanguage


class MetadataLanguageSerializer(serializers.ModelSerializer):
    class Meta:
        model = MetadataLanguage
        fields = (
            'name',
            'fuga_code',
            'iso_639_1',
            'sort_order',
            'is_title_language',
            'is_lyrics_language',
        )
