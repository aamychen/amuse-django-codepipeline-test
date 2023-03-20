from rest_framework import serializers

from amuse.api.v4.serializers.country import CountryV1Serializer
from amuse.api.v4.serializers.subscription_plan import SubscriptionPlanSerializer
from payments.models import PaymentTransaction


# This serializer is not a clean map to model because it replaced
# api.v4.serializers.subscription.CurrentSubscriptionSerializer
# and client developers have more pressing issues (2020-03-05)
class SubscriptionImpostorSerializer(serializers.Serializer):
    payment_expiry_date = serializers.CharField()
    payment_method = serializers.CharField()
    payment_summary = serializers.CharField()
    plan = SubscriptionPlanSerializer()
    paid_until = serializers.DateField()


class PaymentTransactionSerializer(serializers.ModelSerializer):
    country = CountryV1Serializer()
    currency = serializers.CharField(source='get_currency_display')
    subscription = SubscriptionImpostorSerializer(source='payment_method_and_plan')
    type = serializers.CharField(source='get_type_display')
    vat_percentage = serializers.DecimalField(max_digits=4, decimal_places=2)

    class Meta:
        model = PaymentTransaction
        fields = (
            'amount',
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
