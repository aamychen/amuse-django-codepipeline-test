from decimal import Decimal

from rest_framework import serializers

from amuse.api.v4.serializers.country import CountryV1Serializer
from amuse.api.v5.serializers.subscription_plan import SubscriptionPlanSerializer
from payments.models import PaymentTransaction


class SubscriptionImpostorSerializer(serializers.Serializer):
    payment_expiry_date = serializers.DateField(required=False, allow_null=True)
    payment_method = serializers.CharField(required=False, allow_null=True)
    payment_summary = serializers.CharField(required=False, allow_null=True)
    plan = serializers.SerializerMethodField()
    paid_until = serializers.DateField(required=False, allow_null=True)

    def get_plan(self, data):
        plan = SubscriptionPlanSerializer(
            self.context['plan'],
            context={'country': self.context['country']},
            many=False,
        )
        return plan.data


class PaymentTransactionSerializer(serializers.ModelSerializer):
    country = CountryV1Serializer()
    currency = serializers.SerializerMethodField()
    amount_display = serializers.SerializerMethodField()
    vat_amount_display = serializers.SerializerMethodField()
    subscription = serializers.SerializerMethodField()
    type = serializers.CharField(source='get_type_display')
    vat_percentage = serializers.DecimalField(max_digits=4, decimal_places=2)

    def get_currency(self, transaction):
        return transaction.currency.code

    def get_amount_display(self, transaction):
        amount = '{:f}'.format(Decimal(transaction.amount).normalize())
        currency = transaction.currency.code
        return f'{currency} {amount}'

    def get_vat_amount_display(self, transaction):
        if (
            transaction.country.code == 'SE'
            and transaction.currency.code != 'SEK'
            and transaction.vat_amount_sek is not None
        ):
            amount = '{:f}'.format(Decimal(transaction.vat_amount_sek).normalize())
            return f'SEK {amount}'

        amount = '{:f}'.format(Decimal(transaction.vat_amount).normalize())
        currency = transaction.currency.code
        return f'{currency} {amount}'

    def get_subscription(self, transaction):
        data = transaction.payment_method_and_plan()
        subscription = SubscriptionImpostorSerializer(
            data=data,
            context={'country': transaction.country.code, 'plan': transaction.plan},
            many=False,
        )
        subscription.is_valid(raise_exception=True)
        return subscription.data

    class Meta:
        model = PaymentTransaction
        fields = (
            'amount',
            'amount_display',
            'vat_amount_display',
            'country',
            'created',
            'currency',
            'external_transaction_id',
            'id',
            'status',
            'subscription',
            'type',
            'vat_amount',
            'vat_percentage',
        )
