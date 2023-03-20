import logging

from rest_framework import permissions, status
from rest_framework.views import APIView
from rest_framework.generics import GenericAPIView
from rest_framework.response import Response

from amuse import mixins as logmixins
from amuse.api.base.views.exceptions import (
    WrongAPIversionError,
    WithdrawalMethodNotSupported,
)
from amuse.vendor.revenue.client import get_transactions, get_wallet

from amuse.api.v5.serializers.transactions_statement import (
    CreateStatementRequestSerializer,
)


logger = logging.getLogger(__name__)


class RetrieveTransactions(logmixins.LogMixin, APIView):
    allowed_methods = ["GET"]
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, user_id, year_month=None, format=None):
        if self.request.version == "4":
            transactions = get_wallet(
                user_id=self.request.user.pk, year_month=year_month
            )
        else:
            raise WrongAPIversionError()

        return Response(transactions, content_type="application/json")


class CreateWithdrawal(logmixins.LogMixin, APIView):
    allowed_methods = ["POST"]
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, *args, **kwargs):
        raise WithdrawalMethodNotSupported()


class CreateStatementRequest(logmixins.LogMixin, GenericAPIView):
    allowed_methods = ["POST"]
    permission_classes = [permissions.IsAuthenticated]

    def get_serializer_class(self):
        if self.request.version != '5':
            raise WrongAPIversionError()

        return CreateStatementRequestSerializer

    def post(self, request, user_id):
        serializer = self.get_serializer(data=request.data)

        serializer.is_valid(raise_exception=True)
        data = serializer.request_statement()
        if data['is_success']:
            return Response(data, status=status.HTTP_201_CREATED)
        else:
            return Response(data, status.HTTP_400_BAD_REQUEST)
