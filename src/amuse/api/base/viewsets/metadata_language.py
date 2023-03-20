from amuse.api.v5.serializers.metadata_language import MetadataLanguageSerializer
from releases.models import MetadataLanguage
from rest_framework import mixins, permissions, viewsets


class MetadataLanguageViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    permission_classes = (permissions.AllowAny,)
    queryset = MetadataLanguage.objects.all().order_by('sort_order')
    serializer_class = MetadataLanguageSerializer
