from rest_framework import serializers
from django.conf import settings
from amuse.logging import logger
from decimal import ROUND_DOWN, Decimal
from payouts.models import Payee, Event, Payment, TransferMethod
from amuse.vendor.hyperwallet.client_factory import HyperWalletEmbeddedClientFactory
from hyperwallet.exceptions import HyperwalletAPIException, HyperwalletException
from amuse.vendor.revenue.client import (
    get_balance,
    record_withdrawal,
    update_withdrawal,
)
from countries.models import Currency
from amuse.api.v5.serializers.transfer_method import GetTransferMethodSerializer
from waffle import switch_is_active, flag_is_active
from payouts.utils import get_hw_exception_code


class CreatePaymentSerializer(serializers.Serializer):
    destination_token = serializers.CharField(required=True)

    def __init__(self, request, *args, **kwargs):
        super().__init__(request, *args, **kwargs)
        self.request = request
        self.user = self.request.user
        self.payee = None
        self.trm = None
        self.withdrawal_amount = Decimal("0.00")
        self.currency = "USD"
        self.hw_client = HyperWalletEmbeddedClientFactory().create(
            country_code=self.user.country
        )
        self.revenue_system_transaction_id = None

    def _get_default_overrides(self):
        """
        In some cases we want to override default behavior:
        1. Some users will have deactivated Hyperwallet payouts
        2. Some users have greater max_amount limit
        3. Deactivate payouts for maintenance
        :return: dict
        """
        is_maintenance_on = switch_is_active('withdrawals:disabled')
        is_excluded_from_hyperwallet = flag_is_active(
            self.request, 'vendor:hyperwallet:excluded'
        )
        max_limit_overriden = flag_is_active(
            self.request, 'vendor:hyperwallet:override-max-limit'
        )
        return {
            "is_maintenance_on": is_maintenance_on,
            "is_user_excluded": is_excluded_from_hyperwallet,
            "is_max_overriden": max_limit_overriden,
        }

    def _init_payment(self, payee, is_royalty_advance=False):
        amuse_payment = Payment.objects.create(
            payee=payee,
            amount=0.00,
            external_id="pmt-init",
            transfer_method=self.trm,
            currency=Currency.objects.get(code=self.currency),
            status="PRE_CREATE",
            payment_type=Payment.TYPE_ADVANCE
            if is_royalty_advance
            else Payment.TYPE_ROYALTY,
        )
        return amuse_payment

    @staticmethod
    def _confirm_payment(amuse_payment_id, pmt_object, revenue_system_transaction_id):
        pmt_db = Payment.objects.get(id=amuse_payment_id)
        pmt_db.status = pmt_object.status
        pmt_db.external_id = pmt_object.token
        pmt_db.amount = pmt_object.amount
        pmt_db.revenue_system_id = revenue_system_transaction_id
        pmt_db.save()
        return pmt_db

    @staticmethod
    def _save_event(pmt_object):
        Event.objects.create(
            object_id=pmt_object.token,
            reason="API call",
            initiator="SYSTEM",
            payload=pmt_object._raw_json,
        )

    def _get_payee(self, amuse_user):
        try:
            payee = Payee.objects.get(user=amuse_user)
            self.payee = payee
            return payee
        except Exception as e:
            return

    def _get_trm(self, trm_token):
        try:
            self.trm = TransferMethod.objects.get(
                external_id=trm_token,
                payee__pk=self.user.id,
            )
        except Exception as e:
            return

    def _get_balance(self):
        balance = get_balance(self.user.pk)
        if balance is None:
            return Decimal('0')
        # Round down to closest cent
        return Decimal(balance).quantize(Decimal('.01'), rounding=ROUND_DOWN)

    @staticmethod
    def _record_withdrawal(payload):
        return record_withdrawal(payload, is_pending=True)

    def _validate_payee(self):
        payee = self._get_payee(self.user)
        if payee is None:
            raise serializers.ValidationError(
                detail="Payee account does not exist in DB",
                code="PAYEE_DOES_NOT_EXIST_DB",
            )

        if payee.status in ["LOCKED", "DE_ACTIVATED", "FROZEN"]:
            raise serializers.ValidationError(
                detail="Payee account status is invalid state",
                code="INVALID_PAYEE_ACCOUNT_STATUS",
            )

    def _validate_trm(self, trm_token):
        self._get_trm(trm_token=trm_token)
        if self.trm is None:
            raise serializers.ValidationError(
                detail="Transfer method does not exist in DB",
                code="TRM_DOES_NOT_EXIST_DB",
            )

    def validate(self, data):
        overrides = self._get_default_overrides()
        user_id = self.user.id
        trm_token = data['destination_token']

        if overrides['is_maintenance_on']:
            raise serializers.ValidationError(
                detail="You cannot make withdrawals at the moment due to maintenance. Please try again later. Thank you for your patience!",
                code="PAYOUTS_MAINTENANCE",
            )

        if overrides['is_user_excluded']:
            raise serializers.ValidationError(
                detail=f"Hyperwallet payouts disabled for user {user_id}",
                code="PAYOUTS_USER_EXCLUDED",
            )
        self._validate_payee()
        self._validate_trm(trm_token=trm_token)

        # Get user balance from revenue system
        self.withdrawal_amount = self._get_balance()

        if self.withdrawal_amount is None or self.withdrawal_amount <= 0:
            raise serializers.ValidationError(
                detail=f"User {user_id} withdrawal failed: Balance less than or equal to zero: {self.withdrawal_amount}",
                code="INVALID_BALANCE",
            )
        self.withdrawal_amount = Decimal(self.withdrawal_amount)
        limits_and_fee = self.trm.get_limits_and_fee()
        min_amount_with_fee = limits_and_fee['min_amount'] + limits_and_fee['fee']
        max_amount = limits_and_fee['max_amount']
        if overrides['is_max_overriden']:
            max_amount = settings.HYPERWALLET_VERIFIED_USERS_MAX_WITHDRAWAL_LIMIT

        # Validate amount against min_amount limit with fee added
        if self.withdrawal_amount < min_amount_with_fee:
            raise serializers.ValidationError(
                detail=f"User {user_id} withdrawal failed: Balance: {self.withdrawal_amount} less then min_amount:{min_amount_with_fee}",
                code="INVALID_BALANCE_MIN_LIMIT",
            )
        # Validate amount against max_amount limit
        if self.withdrawal_amount > max_amount:
            raise serializers.ValidationError(
                detail=f"User {user_id} withdrawal failed: Balance: {self.withdrawal_amount} greater then max_amount:{max_amount} allowed",
                code="INVALID_BALANCE_MAX_LIMIT",
            )

        return data

    def save(self, is_royalty_advance=False, **kwargs):
        amount = self.withdrawal_amount
        destination_token = self.validated_data['destination_token']
        amuse_payment = self._init_payment(
            payee=self.payee, is_royalty_advance=is_royalty_advance
        )

        try:
            revenue_payload = {
                "user_id": self.user.id,
                "total": self.withdrawal_amount,
                "description": "",
                "currency": self.currency,
                "withdrawal_reference": str(amuse_payment.id),
            }
            logger.info(f'Creating pending revenue payment. payload: {revenue_payload}')

            # Only manually manage transaction on revenue side if its not an advance.
            if not is_royalty_advance:
                self.revenue_system_transaction_id = self._record_withdrawal(
                    revenue_payload
                )
                if self.revenue_system_transaction_id is None:
                    return {
                        "is_success": False,
                        "data": None,
                        "reason": "Unable to record transaction on slayer",
                    }

            hw_data = {
                "amount": str(amount),
                "clientPaymentId": str(amuse_payment.id),
                "currency": self.currency,
                "destinationToken": destination_token,
                "programToken": self.hw_client.programToken,
                "purpose": "OTHER",
            }
            logger.info(f'Creating HW payment. payload: {hw_data}')
            pmt_object = self.hw_client.createPayment(data=hw_data)
            self._save_event(pmt_object=pmt_object)
            pmt_db = self._confirm_payment(
                amuse_payment_id=amuse_payment.id,
                pmt_object=pmt_object,
                revenue_system_transaction_id=self.revenue_system_transaction_id,
            )

            # If payment instantly completed, update revenue system
            if pmt_object.status == "COMPLETED":
                if not is_royalty_advance:
                    update_withdrawal(
                        self.revenue_system_transaction_id, "is_completed"
                    )

            return {
                "is_success": True,
                "data": GetPaymentSerializer(pmt_db).to_representation(pmt_db),
                "reason": None,
            }
        except (HyperwalletAPIException, HyperwalletException) as e:
            # Only cancel if error code indicates payment did not pass on HW side
            error_code = get_hw_exception_code(e)
            should_cancel_payment = (
                error_code in settings.HYPERWALLET_CANCEL_ERROR_CODES
            )
            if not is_royalty_advance and should_cancel_payment:
                update_withdrawal(self.revenue_system_transaction_id, "is_cancelled")
            return {
                "is_success": False,
                "data": None,
                "reason": e.message,
                "cancel_revenue_payment": should_cancel_payment,
            }
        except Exception as e:
            return {"is_success": False, "data": None, "reason": e.__str__()}


class GetPaymentSerializer(serializers.ModelSerializer):
    currency = serializers.CharField(source='get_currency_display')
    transfer_method = GetTransferMethodSerializer()

    class Meta:
        model = Payment
        fields = [
            'id',
            'payee_id',
            'external_id',
            'amount',
            'currency',
            'status',
            'transfer_method',
            'created',
        ]
