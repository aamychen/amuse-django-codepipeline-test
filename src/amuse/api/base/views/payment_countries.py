from rest_framework import generics, status
from rest_framework.decorators import permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from amuse import mixins as logmixins
from amuse.api.base.views.exceptions import WrongAPIversionError
from amuse.api.v4.serializers.country import CountrySerializer
from countries.models import Country


@permission_classes([IsAuthenticated])
class PaymentCountriesView(logmixins.LogMixin, generics.GenericAPIView):
    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        if not self.request.version == '4':
            raise WrongAPIversionError()

    def get(self, request, *args, **kwargs):
        countries = Country.objects.filter(is_adyen_enabled=True).order_by('name')
        detected_country = request.META.get('HTTP_CF_IPCOUNTRY')

        if detected_country:
            if detected_country not in [c.code for c in countries]:
                detected_country = countries[0].code
        else:
            detected_country = countries[0].code

        response = {
            'available_countries': CountrySerializer(countries, many=True).data,
            'detected_country': detected_country,
        }

        return Response(response, status=status.HTTP_200_OK)
