from rest_framework import serializers
from releases.models import Genre


class GenreSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField()


class GenreListSerializer(GenreSerializer):
    subgenres = GenreSerializer(many=True)

    class Meta:
        model = Genre
        fields = ('id', 'name', 'subgenres')
