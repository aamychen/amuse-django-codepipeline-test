from rest_framework import status
from rest_framework.decorators import permission_classes
from rest_framework.generics import GenericAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from amuse.api.base.views.exceptions import WrongAPIversionError
from amuse.api.v5.serializers.transfer_method import (
    CreateTransferMethodSerializer,
    GetTransferMethodSerializer,
    UpdateTransferMethodSerializer,
)
from payouts.models import Payee, TransferMethod
from amuse.mixins import LogMixin


@permission_classes([IsAuthenticated])
class TransferMethodView(LogMixin, GenericAPIView):
    def get_serializer_class(self):
        if not self.request.version == '5':
            raise WrongAPIversionError()

        return CreateTransferMethodSerializer

    def _get_payee(self, user):
        try:
            payee = Payee.objects.get(pk=user.id)
            return payee.external_id
        except Exception as e:
            return None

    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.save()
        if data['is_success']:
            return Response(data, status=status.HTTP_201_CREATED)
        else:
            return Response(data, status.HTTP_404_NOT_FOUND)

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
        trm_qs = TransferMethod.objects.filter(payee__pk=user.pk, active=True)
        self.serializer_class = GetTransferMethodSerializer(trm_qs, many=True)
        return Response(
            {
                "is_success": True,
                "transfer_methods": self.serializer_class.to_representation(trm_qs),
            },
            status.HTTP_200_OK,
        )

    def put(self, request):
        serializer = UpdateTransferMethodSerializer(data=self.request.data)
        serializer.is_valid(raise_exception=True)
        try:
            instance = TransferMethod.objects.get(external_id=serializer.data['token'])
            data = serializer.update(instance, self.request.data)
            if data['is_success']:
                return Response(data, status=status.HTTP_200_OK)
            else:
                return Response(data, status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response(
                {
                    "is_success": False,
                    "reason": str(e),
                },
                status.HTTP_400_BAD_REQUEST,
            )
