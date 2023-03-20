from rest_framework import status
from rest_framework import serializers
from rest_framework.decorators import permission_classes
from rest_framework.generics import GenericAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.conf import settings
from hyperwallet.exceptions import HyperwalletAPIException
from amuse.api.base.views.exceptions import WrongAPIversionError
from amuse.api.v5.serializers.payout_payment import (
    CreatePaymentSerializer,
    GetPaymentSerializer,
)
from payouts.models import Payee, TransferMethod, Payment
from amuse.mixins import LogMixin


@permission_classes([IsAuthenticated])
class PaymentView(LogMixin, GenericAPIView):
    def get_serializer_class(self):
        if not self.request.version == '5':
            raise WrongAPIversionError()

        return CreatePaymentSerializer

    @staticmethod
    def _get_payee(user):
        try:
            payee = Payee.objects.get(pk=user.id)
            return payee.external_id
        except Exception as e:
            return None

    def post(self, request):
        serializer = self.get_serializer(request=request, data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.save()
        if data['is_success']:
            return Response(data, status=status.HTTP_201_CREATED)
        else:
            return Response(data, status.HTTP_400_BAD_REQUEST)

    def get(self, request):
        user = self.request.user
        if self._get_payee(user=user) is None:
            return Response(
                {
                    "is_success": False,
                    "reason": "HW user not found",
                },
                status.HTTP_404_NOT_FOUND,
            )
        pmt_qs = (
            Payment.objects.filter(payee__pk=user.pk)
            .exclude(status='PRE_CREATE')
            .order_by('-created')
        )
        self.serializer_class = GetPaymentSerializer(pmt_qs, many=True)
        return Response(
            {
                "is_success": True,
                "payments": self.serializer_class.to_representation(pmt_qs),
            },
            status.HTTP_200_OK,
        )
