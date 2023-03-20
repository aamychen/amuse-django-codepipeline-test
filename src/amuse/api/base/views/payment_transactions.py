import logging

from rest_framework import generics, status
from rest_framework.decorators import permission_classes
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from amuse import mixins as logmixins
from amuse.analytics import (
    subscription_new_intro_started,
    subscription_new_started,
    subscription_payment_method_changed,
)
from amuse.api.base.views.exceptions import WrongAPIversionError
from amuse.api.v4.serializers.payment_transaction import (
    PaymentTransactionSerializer as PaymentTransactionV4Serializer,
)
from amuse.api.v5.serializers.payment_transaction import (
    PaymentTransactionSerializer as PaymentTransactionV5Serializer,
)
from amuse.platform import PlatformHelper
from amuse.utils import get_ip_address
from amuse.vendor.adyen import authorise_3ds
from payments.models import PaymentTransaction
from subscriptions.models import Subscription


logger = logging.getLogger(__name__)


@permission_classes([IsAuthenticated])
class PaymentTransactionView(logmixins.LogMixin, generics.ListAPIView):
    def get_serializer_class(self):
        if self.request.version == '4':
            return PaymentTransactionV4Serializer
        elif self.request.version == '5':
            return PaymentTransactionV5Serializer
        else:
            raise WrongAPIversionError()

    def get_queryset(self):
        return PaymentTransaction.objects.filter(
            subscription__provider=Subscription.PROVIDER_ADYEN,
            status=PaymentTransaction.STATUS_APPROVED,
            type__in=(
                PaymentTransaction.TYPE_AUTHORISATION,
                PaymentTransaction.TYPE_PAYMENT,
                PaymentTransaction.TYPE_INTRODUCTORY_PAYMENT,
                PaymentTransaction.TYPE_FREE_TRIAL,
            ),
            user=self.request.user,
        ).order_by('-created')

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        if self.request.version not in ['4', '5']:
            raise WrongAPIversionError()

    def get(self, request, *args, **kwargs):
        try:
            return self.list(request, *args, **kwargs)
        except ValueError as err:
            # one of the Plans doesn't have Price Card for the Country provided
            raise ValidationError(err)


class UpdatePaymentTransactionView(logmixins.LogMixin, generics.UpdateAPIView):
    def get_object(self):
        return PaymentTransaction.objects.get(
            user=self.request.user, pk=self.kwargs['transaction_id']
        )

    def partial_update(self, request, *args, **kwargs):
        transaction_id = self.kwargs['transaction_id']
        logger.info(
            f'Adyen 3DS for PaymentTransaction {transaction_id}: {request.data}'
        )

        payment = self.get_object()
        response = authorise_3ds(request.data, payment)

        if response['is_success']:
            subscription = payment.subscription
            payment_count = subscription.paymenttransaction_set.filter(
                status=PaymentTransaction.STATUS_APPROVED
            ).count()

            if payment_count == 1:
                latest_payment = subscription.latest_payment()
                latest_payment.category = PaymentTransaction.CATEGORY_INITIAL
                latest_payment.save()

            self.trigger_analytics(request, payment_count, payment, subscription)

        return Response(response, status=status.HTTP_200_OK)

    def trigger_analytics(self, request, payment_count, payment, subscription):
        client = request.META.get('HTTP_USER_AGENT', '')
        ip_address = get_ip_address(request)

        if payment_count != 1:
            subscription_payment_method_changed(subscription, client, ip_address)
            return

        latest_payment = subscription.latest_payment()

        platform = PlatformHelper.from_payment(latest_payment)
        subscription_new_event = (
            subscription_new_intro_started
            if latest_payment.is_introductory
            else subscription_new_started
        )
        subscription_new_event(
            subscription, platform, client, ip_address, payment.currency.code
        )
