from rest_framework import status
from rest_framework.decorators import permission_classes
from rest_framework.generics import CreateAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from amuse import mixins as logmixins
from amuse.api.base.views.exceptions import WrongAPIversionError
from amuse.api.v5.serializers.subscription import AppleSubscriptionInfoRequestSerializer
from amuse.vendor.apple.exceptions import UnknownAppleError, MaxRetriesExceededError
from amuse.vendor.apple.subscriptions import AppleReceiptValidationAPIClient


@permission_classes([IsAuthenticated])
class AppleSubscriptionInfoView(logmixins.LogMixin, CreateAPIView):
    def get_serializer_class(self):
        if self.request.version not in ['5']:
            raise WrongAPIversionError()

        return AppleSubscriptionInfoRequestSerializer

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        receipt = serializer.validated_data['receipt_data']

        client = AppleReceiptValidationAPIClient(receipt, max_retries=1)
        try:
            client.validate_receipt()
        except (UnknownAppleError, MaxRetriesExceededError):
            return Response(status=status.HTTP_400_BAD_REQUEST)

        is_introductory_offer_eligible = client.is_introductory_offer_eligible()
        data = {'is_introductory_offer_eligible': is_introductory_offer_eligible}

        return Response(data=data, status=status.HTTP_200_OK)
