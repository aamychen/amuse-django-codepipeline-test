from django.db.models import F
from rest_framework import generics
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from amuse import mixins as logmixins
from amuse.api.base.views.exceptions import WrongAPIversionError
from amuse.api.v4.serializers.subscription_plan import (
    SubscriptionPlanSerializer as SubscriptionPlanV4Serializer,
)
from amuse.api.v5.serializers.subscription_plan import (
    SubscriptionPlanSerializer as SubscriptionPlanV5Serializer,
)
from countries.models import Country
from subscriptions.models import SubscriptionPlan


class SubscriptionPlansView(logmixins.LogMixin, generics.ListAPIView):
    pagination_class = None
    permission_classes = []
    queryset = SubscriptionPlan.objects.filter(is_public=True)

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        if self.request.version not in ['4', '5']:
            raise WrongAPIversionError()

    def get_serializer_class(self):
        if self.request.version == '4':
            return SubscriptionPlanV4Serializer
        elif self.request.version == '5':
            return SubscriptionPlanV5Serializer
        else:
            raise WrongAPIversionError()

    def get_serializer(self, *args, **kwargs):
        serializer_class = self.get_serializer_class()
        kwargs['context'] = self.get_serializer_context()

        if serializer_class is SubscriptionPlanV5Serializer:
            country = self._get_country_code(self.request)
            kwargs['context']['country'] = country

        return serializer_class(*args, **kwargs)

    def filter_queryset(self, queryset):
        """
        If a Plan on V5 doesn't have a PriceCard for the Country provided,
        exclude it from the queryset instead of raising a ValidationError
        """

        queryset = super().filter_queryset(queryset)
        queryset = queryset.filter(
            pricecard__introductorypricecard__isnull=True
        ).distinct()
        if self.request.version == '5':
            country_code = self._get_country_code(self.request)
        else:
            country_code = 'US'

        filtered_queryset = queryset.filter(pricecard__countries__code=country_code)
        if not filtered_queryset.exists():
            # we don't have any plans for this Country
            # instead of returning [], return Plans for US as a global default
            filtered_queryset = queryset.filter(pricecard__countries__code='US')
        return filtered_queryset

    def list(self, request, *args, **kwargs):
        try:
            queryset = self.filter_queryset(self.get_queryset())

            serializer = self.get_serializer(queryset, many=True)
            data = self._get_data_with_best_deals(queryset, serializer.data)

            return Response(data)
        except ValueError as err:
            # one of the Plans doesn't have Price Card for the Country provided
            raise ValidationError(err)

    def _get_country_code(self, request):
        country_id = request.query_params.get('country')
        if not country_id:
            country_id = request.META.get('HTTP_CF_IPCOUNTRY', 'US')

        try:
            country = Country.objects.get(code=country_id)
            return country.code
        except Country.DoesNotExist:
            raise ValidationError(f'Invalid Country: {country_id}')

    def _get_data_with_best_deals(self, queryset, data):
        if queryset.exists():
            best_deal_id = (
                queryset.order_by(F("pricecard__price") / F("period")).first().id
            )

            for plan in data:
                plan["best_deal"] = plan["id"] == best_deal_id
        return data
