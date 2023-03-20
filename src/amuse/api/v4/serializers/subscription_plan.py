from rest_framework import serializers

from subscriptions.models import SubscriptionPlan


class SubscriptionPlanSerializer(serializers.ModelSerializer):
    apple_product_id = serializers.SerializerMethodField()
    price = serializers.SerializerMethodField()

    def get_apple_product_id(self, plan):
        if 'request' not in self.context:
            return plan.apple_product_id

        user = self.context['request'].user
        if user.is_anonymous:
            return plan.apple_product_id
        return plan.apple_product_id_notrial

    def get_price(self, plan):
        return str(plan.get_price_card().price)

    class Meta:
        model = SubscriptionPlan
        fields = (
            'id',
            'name',
            'price',
            'period',
            'trial_days',
            'apple_product_id',
            'google_product_id',
        )
