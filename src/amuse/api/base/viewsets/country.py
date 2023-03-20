from amuse.api.v4.serializers.country import CountryV1Serializer
from countries.models import Country
from rest_framework import mixins, permissions, viewsets


class CountryViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    permission_classes = (permissions.AllowAny,)
    queryset = Country.objects.all().order_by('name')
    serializer_class = CountryV1Serializer
