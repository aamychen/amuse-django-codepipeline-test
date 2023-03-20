from decimal import Decimal

from django.test import TestCase

from amuse.api.v4.serializers.subscription_plan import SubscriptionPlanSerializer
from subscriptions.tests.factories import SubscriptionPlanFactory


class TestSubscriptionPlanSerializer(TestCase):
    def test_serialize(self):
        plan = SubscriptionPlanFactory()
        serialized = SubscriptionPlanSerializer(plan).data

        self.assertEqual(serialized['id'], plan.pk)
        self.assertEqual(serialized['name'], plan.name)
        self.assertEqual(serialized['period'], plan.period)
        self.assertEqual(serialized['price'], str(plan.get_price_card().price))
        self.assertEqual(serialized['trial_days'], plan.trial_days)
        self.assertEqual(serialized['apple_product_id'], plan.apple_product_id)
        self.assertEqual(serialized['google_product_id'], plan.google_product_id)
