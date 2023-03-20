from rest_framework import status
from rest_framework.decorators import permission_classes
from rest_framework.exceptions import ValidationError
from rest_framework.generics import ListAPIView, UpdateAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from amuse import mixins as logmixins
from amuse.analytics import subscription_payment_method_changed
from amuse.api.base.views.exceptions import (
    NoActiveSubscriptionExistsError,
    WrongAPIversionError,
)
from amuse.api.v4.serializers.subscription import (
    AdyenPaymentMethodsSerializer,
    UpdateSubscriptionPaymentMethodSerializer,
)
from amuse.permissions import CanManageAdyenSubscription
from amuse.utils import get_ip_address, parse_client_version
from amuse.vendor.adyen import authorise_payment_method, get_payment_methods


@permission_classes([IsAuthenticated])
class BasePaymentMethodView(UpdateAPIView):
    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        if self.request.version not in ['4', '5']:
            raise WrongAPIversionError()


@permission_classes([IsAuthenticated, CanManageAdyenSubscription])
class UpdatePaymentMethodView(logmixins.LogMixin, BasePaymentMethodView, UpdateAPIView):
    serializer_class = UpdateSubscriptionPaymentMethodSerializer

    def get_object(self):
        subscription = self.request.user.current_subscription()
        if not subscription or subscription.is_free:
            raise NoActiveSubscriptionExistsError()
        else:
            return subscription

    def update(self, request, *args, **kwargs):
        subscription = self.get_object()
        serializer = self.get_serializer(subscription, data=request.data)
        serializer.is_valid(raise_exception=True)
        return self.perform_update(serializer)

    def perform_update(self, serializer):
        ip_address = get_ip_address(self.request)
        localised = self.request.version == '5'
        response = authorise_payment_method(
            self.request.user,
            serializer.validated_data['payment_details']['paymentMethod'],
            serializer.validated_data['country'],
            parse_client_version(self.request.META.get('HTTP_USER_AGENT', ''))[0],
            ip_address,
            serializer.validated_data['payment_details'].get('browserInfo'),
            serializer.validated_data.get('return_url'),
            localised=localised,
            billing_address=serializer.validated_data['payment_details'].get(
                'billingAddress'
            ),
        )

        if response['is_success']:
            subscription_payment_method_changed(
                self.get_object(),
                self.request.META.get('HTTP_USER_AGENT', ''),
                ip_address,
            )
            return Response(status=status.HTTP_204_NO_CONTENT)
        elif not response['is_success'] and 'action' in response:
            return Response(response, status=status.HTTP_200_OK)
        else:
            # TODO: We need to figure out how to handle different types of errors.
            return Response(response, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class GetSupportedPaymentMethodView(
    logmixins.LogMixin, BasePaymentMethodView, ListAPIView
):
    serializer_class = AdyenPaymentMethodsSerializer

    def list(self, request, *args, **kwargs):
        try:
            serializer = self.get_serializer(data=request.GET)
            serializer.is_valid(raise_exception=True)
            localised = self.request.version == '5'
            payment_methods = get_payment_methods(
                serializer.validated_data['subscription_plan'],
                serializer.validated_data['country'].code,
                parse_client_version(request.META.get('HTTP_USER_AGENT', ''))[0],
                localised=localised,
            )
            return Response(payment_methods, status=status.HTTP_200_OK)
        except ValueError as err:
            # one of the Plans doesn't have Price Card for the Country provided
            raise ValidationError(err)
