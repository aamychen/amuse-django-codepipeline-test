from rest_framework import serializers
from amuse.logging import logger
from decimal import ROUND_DOWN, Decimal
from amuse.vendor.hyperwallet.client_factory import HyperWalletEmbeddedClientFactory
from slayer.clientwrapper import update_royalty_advance_offer
from amuse.api.v5.serializers.payout_payment import CreatePaymentSerializer
from payouts.ffwd import FFWDHelpers


class FFWDOfferAcceptSerializer(CreatePaymentSerializer):
    offer_id = serializers.UUIDField(required=True, format='hex_verbose')
    destination_token = serializers.CharField(required=True)

    def __init__(self, request, *args, **kwargs):
        super().__init__(request, *args, **kwargs)
        self.request = request
        self.user = self.request.user
        self.hw_client = HyperWalletEmbeddedClientFactory().create(
            country_code=self.user.country
        )

    def validate(self, data):
        trm_token = data['destination_token']
        self._validate_payee()
        self._validate_trm(trm_token=trm_token)
        return data

    def save(self, **kwargs):
        validate_response = FFWDHelpers.validate_royalty_advance_offer(
            self.user.id, str(self.validated_data['offer_id'])
        )

        advance_id = validate_response['advance_id']
        raw_withdrawal_total = validate_response['raw_withdrawal_total']
        self.revenue_system_transaction_id = advance_id
        self.withdrawal_amount = abs(Decimal(raw_withdrawal_total)).quantize(
            Decimal('.01'), rounding=ROUND_DOWN
        )

        # Call into the CreatePayment serializer to handle HW payment creation
        withdrawal_response = super().save(is_royalty_advance=True, **kwargs)

        if withdrawal_response['is_success']:
            logger.info(f"FFWD offer accepted successfully id: {advance_id}")

        if not withdrawal_response['is_success']:
            should_cancel_payment = withdrawal_response.get('cancel_revenue_payment')
            if should_cancel_payment:
                cancellation_response = update_royalty_advance_offer(
                    self.user.id,
                    advance_id,
                    "cancel",
                    description="New Hyperwallet API integration API",
                )
                logger.warn(
                    f"FFWD accept failed: Payment: {withdrawal_response} Slayer response: {cancellation_response}"
                )
                FFWDHelpers.unlock_splits(self.user.id)
        return withdrawal_response
