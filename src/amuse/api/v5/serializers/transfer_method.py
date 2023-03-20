from rest_framework import serializers
from amuse.logging import logger
from payouts.models import Payee, Event, TransferMethod
from amuse.vendor.hyperwallet.client_factory import HyperWalletEmbeddedClientFactory
from hyperwallet.exceptions import HyperwalletAPIException
from countries.models import Currency


class CreateTransferMethodSerializer(serializers.Serializer):
    token = serializers.CharField(required=True)
    type = serializers.CharField(required=True)

    def validate(self, data):
        trm_token = data['token']
        qs = TransferMethod.objects.filter(external_id=trm_token, active=True)
        if qs.count() > 0:
            raise serializers.ValidationError(
                detail=f"{trm_token} already exist", code="TRM_EXIST_IN_DB"
            )
        return data

    @staticmethod
    def _get_currency(code):
        currency = Currency.objects.filter(code=code).last()
        if currency is not None:
            return currency
        else:
            return Currency.objects.filter(code='USD').last()

    def _save_transfer_method(self, payee, trm_object):
        try:
            trm_db = TransferMethod.objects.get(external_id=trm_object.token)
            trm_db.active = True
            trm_db.save()
        except TransferMethod.DoesNotExist:
            currency = self._get_currency(trm_object.transferMethodCurrency)
            TransferMethod.objects.create(
                payee=payee,
                external_id=trm_object.token,
                type=trm_object.type,
                status=trm_object.status,
                provider=payee.provider,
                currency=currency,
            )
        # Deactivate all other methods
        qs = TransferMethod.objects.filter(payee=payee).exclude(
            external_id=trm_object.token
        )
        if qs.count() > 0:
            qs.update(active=False)

    @staticmethod
    def _save_event(trm_object):
        Event.objects.create(
            object_id=trm_object.token,
            reason="API call",
            initiator="SYSTEM",
            payload=trm_object._raw_json,
        )

    @staticmethod
    def _get_payee(amuse_user):
        try:
            payee = Payee.objects.get(user=amuse_user)
            return payee
        except Exception as e:
            return

    def save(self, **kwargs):
        request = self.context['request']
        trm_token = self.validated_data['token']
        type = self.validated_data['type']
        amuse_user = request.user
        payee = self._get_payee(amuse_user)
        if payee is None:
            return {
                "is_success": False,
                "data": None,
                "reason": "HW user does not exit in DB",
            }
        hw_client = HyperWalletEmbeddedClientFactory().create(
            country_code=amuse_user.country
        )

        try:
            if type == 'PAYPAL_ACCOUNT':
                trm_object = hw_client.getPayPalAccount(
                    userToken=payee.external_id,
                    payPalAccountToken=trm_token,
                )
            elif type == 'BANK_ACCOUNT':
                trm_object = hw_client.getBankAccount(
                    userToken=payee.external_id,
                    bankAccountToken=trm_token,
                )
            elif type == 'WIRE_ACCOUNT':
                trm_object = hw_client.getBankAccount(
                    userToken=payee.external_id,
                    bankAccountToken=trm_token,
                )
            elif type == 'BANK_CARD':
                trm_object = hw_client.getBankCard(
                    userToken=payee.external_id, bankCardToken=trm_token
                )
            elif type == 'VENMO_ACCOUNT':
                trm_object = hw_client.getVenmoAccount(
                    userToken=payee.external_id, venmoAccountToken=trm_token
                )
            elif type == 'PREPAID_CARD':
                trm_object = hw_client.getPrepaidCard(
                    userToken=payee.external_id, prepaidCardToken=trm_token
                )
            elif type == 'PAPER_CHECK':
                trm_object = hw_client.getPaperCheck(
                    userToken=payee.external_id, paperCheckToken=trm_token
                )
            else:
                return {
                    "is_success": False,
                    "data": None,
                    "reason": "Unsupported transfer method",
                }
            self._save_event(trm_object=trm_object)
            self._save_transfer_method(payee=payee, trm_object=trm_object)
            return {"is_success": True, "data": trm_object.asDict(), "reason": None}
        except HyperwalletAPIException as e:
            return {"is_success": False, "data": None, "reason": e.message}
        except Exception as e:
            return {"is_success": False, "data": None, "reason": str(e)}


class GetTransferMethodSerializer(serializers.ModelSerializer):
    limits_and_fee = serializers.JSONField(source='get_limits_and_fee')

    class Meta:
        model = TransferMethod
        fields = [
            'payee_id',
            'external_id',
            'type',
            'status',
            'limits_and_fee',
            'created',
            'active',
        ]


class UpdateTransferMethodSerializer(serializers.Serializer):
    token = serializers.CharField(required=True)
    type = serializers.CharField(required=True)

    def validate(self, data):
        return data

    @staticmethod
    def _get_currency(code):
        currency = Currency.objects.filter(code=code).last()
        if currency is not None:
            return currency
        else:
            return Currency.objects.filter(code='USD').last()

    def _update_transfer_method(self, trm_object):
        currency = self._get_currency(trm_object.transferMethodCurrency)
        trm_object_db = TransferMethod.objects.get(external_id=trm_object.token)
        trm_object_db.status = trm_object.status
        trm_object_db.currency = currency
        trm_object_db.type = trm_object.type
        trm_object_db.save()

    @staticmethod
    def _save_event(trm_object):
        Event.objects.create(
            object_id=trm_object.token,
            reason="API call UPDATE",
            initiator="SYSTEM",
            payload=trm_object._raw_json,
        )

    def update(self, instance, validated_data):
        trm_token = self.validated_data['token']
        type = self.validated_data['type']
        payee = instance.payee
        amuse_user = payee.user
        hw_client = HyperWalletEmbeddedClientFactory().create(
            country_code=amuse_user.country
        )

        try:
            if type == 'PAYPAL_ACCOUNT':
                trm_object = hw_client.getPayPalAccount(
                    userToken=payee.external_id,
                    payPalAccountToken=trm_token,
                )
            elif type == 'BANK_ACCOUNT':
                trm_object = hw_client.getBankAccount(
                    userToken=payee.external_id,
                    bankAccountToken=trm_token,
                )
            elif type == 'WIRE_ACCOUNT':
                trm_object = hw_client.getBankAccount(
                    userToken=payee.external_id,
                    bankAccountToken=trm_token,
                )
            elif type == 'BANK_CARD':
                trm_object = hw_client.getBankCard(
                    userToken=payee.external_id, bankCardToken=trm_token
                )
            elif type == 'VENMO_ACCOUNT':
                trm_object = hw_client.getVenmoAccount(
                    userToken=payee.external_id, venmoAccountToken=trm_token
                )
            elif type == 'PREPAID_CARD':
                trm_object = hw_client.getPrepaidCard(
                    userToken=payee.external_id, prepaidCardToken=trm_token
                )
            elif type == 'PAPER_CHECK':
                trm_object = hw_client.getPaperCheck(
                    userToken=payee.external_id, paperCheckToken=trm_token
                )
            else:
                return {
                    "is_success": False,
                    "data": None,
                    "reason": "Unsupported transfer method",
                }
            self._save_event(trm_object=trm_object)
            self._update_transfer_method(trm_object=trm_object)
            return {"is_success": True, "data": trm_object.asDict(), "reason": None}
        except HyperwalletAPIException as e:
            return {"is_success": False, "data": None, "reason": e.message}
        except Exception as e:
            return {"is_success": False, "data": None, "reason": str(e)}
