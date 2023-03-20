from rest_framework import status
from rest_framework.decorators import permission_classes
from rest_framework.generics import GenericAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from hyperwallet.exceptions import HyperwalletAPIException

from amuse.api.base.views.exceptions import WrongAPIversionError
from amuse.api.v5.serializers.payee import (
    CreatePayeeSerializer,
    GetPayeeSerializer,
    UpdatePayeeSerializer,
)
from payouts.models import Payee
from amuse.vendor.hyperwallet.client_factory import HyperWalletEmbeddedClientFactory
from amuse.mixins import LogMixin


@permission_classes([IsAuthenticated])
class PayeeView(LogMixin, GenericAPIView):
    def get_serializer_class(self):
        if not self.request.version == '5':
            raise WrongAPIversionError()

        return CreatePayeeSerializer

    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.save()
        if data['is_success']:
            return Response(data, status=status.HTTP_201_CREATED)
        else:
            return Response(data, status.HTTP_400_BAD_REQUEST)

    def put(self, request):
        user = self.request.user
        serializer = UpdatePayeeSerializer(
            data=self.request.data, context={'user': user}
        )
        serializer.is_valid(raise_exception=True)

        try:
            payee = Payee.objects.get(user=user)
            data = serializer.update(payee, request.data)
            if not data['is_success']:
                return Response(
                    data=data,
                    status=status.HTTP_400_BAD_REQUEST,
                )
            return Response(
                data=data,
                status=status.HTTP_200_OK,
            )

        except Exception as e:
            return Response(
                {"is_success": False, "data": None, "reason": str(e)},
                status=status.HTTP_400_BAD_REQUEST,
            )

    def get(self, request):
        user = self.request.user
        try:
            payee = Payee.objects.get(user=user)
            return Response(
                {
                    'is_success': True,
                    "data": GetPayeeSerializer().to_representation(payee),
                },
                status=status.HTTP_200_OK,
            )

        except Exception as e:
            return Response(
                {'is_success': False, "data": None, "reason": str(e)},
                status=status.HTTP_404_NOT_FOUND,
            )


@permission_classes([IsAuthenticated])
class PayeeGetAuthTokenView(LogMixin, GenericAPIView):
    def _get_payee_token(self, user):
        try:
            payee = Payee.objects.get(pk=user.id)
            return payee.external_id
        except Exception as e:
            return None

    def get(self, request):
        if not self.request.version == '5':
            raise WrongAPIversionError()
        user = self.request.user
        payee_token = self._get_payee_token(user)
        if not payee_token or payee_token == "":
            return Response(
                {'is_success': False, "data": None, "reason": "HW user not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        hw_client = HyperWalletEmbeddedClientFactory().create(country_code=user.country)
        try:
            data = hw_client.getAuthenticationToken(userToken=payee_token)
            return Response(
                {'is_success': True, "data": data.asDict(), "reason": None},
                status=status.HTTP_200_OK,
            )
        except HyperwalletAPIException as e:
            return Response(
                {'is_success': False, "data": None, "reason": e.message},
                status=status.HTTP_200_OK,
            )
