from django.db.models import Prefetch
from amuse.api.v4.serializers.genre import GenreListSerializer
from releases.models import Genre
from rest_framework import mixins, permissions, viewsets


class GenreListViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    permission_classes = (permissions.AllowAny,)
    queryset = Genre.objects.all()
    serializer_class = GenreListSerializer

    def get_queryset(self):
        genres = Genre.objects.filter(
            parent=None, status=Genre.STATUS_ACTIVE
        ).prefetch_related(
            Prefetch(
                'subgenres', queryset=Genre.objects.filter(status=Genre.STATUS_ACTIVE)
            )
        )
        yt_content_id = self.request.query_params.get('yt_content_id', None)
        valid_parameter = yt_content_id in ['exclude', 'only']
        if not valid_parameter:
            return genres

        if yt_content_id == 'only':
            return genres.exclude(name__in=Genre.NO_YT_CONTENT_GENRES)
        else:
            return genres.filter(name__in=Genre.NO_YT_CONTENT_GENRES)
