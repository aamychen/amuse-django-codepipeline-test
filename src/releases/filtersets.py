from django_filters import rest_framework as filters

from releases.models import Release


class ReleaseArtistV2FilterSet(filters.FilterSet):
    artist_id = filters.NumberFilter(field_name='artist_id', method='filter_artist')

    def filter_artist(self, queryset, name, value):
        return queryset.filter(songs__artists__id=value).distinct()

    class Meta:
        model = Release
        fields = ['artist_id']
