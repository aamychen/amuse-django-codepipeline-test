from rest_framework import status
from rest_framework import serializers
from rest_framework.decorators import permission_classes
from rest_framework.generics import GenericAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.conf import settings
from hyperwallet.exceptions import HyperwalletAPIException
from amuse.api.base.views.exceptions import WrongAPIversionError
from amuse.api.v5.serializers.payout_ffwd import (
    FFWDOfferAcceptSerializer,
)
from payouts.models import Payee, TransferMethod, Payment
from amuse.mixins import LogMixin


@permission_classes([IsAuthenticated])
class FFWDView(LogMixin, GenericAPIView):
    def get_serializer_class(self):
        if not self.request.version == '5':
            raise WrongAPIversionError()

        return FFWDOfferAcceptSerializer

    def post(self, request):
        serializer = self.get_serializer(request=request, data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.save()
        if data['is_success']:
            return Response(data, status=status.HTTP_201_CREATED)
        else:
            return Response(data, status.HTTP_400_BAD_REQUEST)
