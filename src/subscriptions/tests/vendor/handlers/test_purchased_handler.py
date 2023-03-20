import base64
from unittest import mock

import responses
from django.test import TestCase

from countries.tests.factories import CountryFactory, CurrencyFactory
from payments.tests.factories import PaymentMethodFactory, PaymentTransactionFactory
from subscriptions.models import Subscription
from subscriptions.tests.factories import (
    SubscriptionFactory,
    SubscriptionPlanFactory,
    UserFactory,
)
from subscriptions.vendor.google import PurchaseSubscription
from subscriptions.vendor.google.enums import SubscriptionNotificationType
from subscriptions.vendor.google.handlers import (
    HandlerArgs,
    PurchasedNotificationHandler,
)
from subscriptions.vendor.google.handlers.purchased_handler_v1 import (
    PurchasedNotificationHandlerV1,
)
from subscriptions.vendor.google.handlers.purchased_handler_v2 import (
    PurchasedNotificationHandlerV2,
)


class TestPurchaseHandlerV1(TestCase):
    @responses.activate
    @mock.patch('amuse.tasks.zendesk_create_or_update_user')
    def setUp(self, _):
        self.notification_type = int(SubscriptionNotificationType.PURCHASED)
        self.event_id = '123x'
        self.purchase_token = 'purchaseToken123'
        self.google_product_id = 'google_monthly'
        self.order_id = 'order123'

        self.handler = PurchasedNotificationHandler(self.event_id)

        self.user = UserFactory()
        self.country = CountryFactory(code='SE')
        self.currency = CurrencyFactory(code='SEK')
        self.payment_method = PaymentMethodFactory(
            external_recurring_id=self.purchase_token, method='GOOGL', user=self.user
        )
        self.plan = SubscriptionPlanFactory(google_product_id=self.google_product_id)

    def create_subscription_and_payment(self, status, grace_period_until):
        self.subscription = SubscriptionFactory(
            user=self.user,
            status=status,
            provider=Subscription.PROVIDER_GOOGLE,
            payment_method=self.payment_method,
            plan=self.plan,
            grace_period_until=grace_period_until,
        )
        self.payment = PaymentTransactionFactory(
            external_transaction_id=self.order_id,
            plan=self.plan,
            subscription=self.subscription,
            user=self.user,
        )

    def create_args(self, payload):
        purchase = PurchaseSubscription(**payload)
        return HandlerArgs(
            notification_type=self.notification_type,
            purchase_token=self.purchase_token,
            google_subscription_id=self.google_product_id,
            purchase=purchase,
        )

    @responses.activate
    @mock.patch('amuse.tasks.zendesk_create_or_update_user')
    @mock.patch.object(PurchasedNotificationHandlerV2, 'handle', return_value=True)
    @mock.patch.object(PurchasedNotificationHandlerV1, 'handle', return_value=True)
    def test_v2_flow(self, mock_flow_v1, mock_flow_v2, _):
        data = self.create_args({})
        result = self.handler.handle(data)

        self.assertEqual(0, mock_flow_v2.call_count)
        self.assertEqual(1, mock_flow_v1.call_count)

    @responses.activate
    @mock.patch('amuse.tasks.zendesk_create_or_update_user')
    @mock.patch.object(PurchasedNotificationHandlerV2, 'handle', return_value=True)
    @mock.patch.object(PurchasedNotificationHandlerV1, 'handle', return_value=True)
    def test_v1_flow(self, mock_flow_v1, mock_flow_v2, _):
        user_id_b64 = base64.b64encode(str(self.user.pk).encode('ascii'))
        data = self.create_args({'obfuscatedExternalAccountId': user_id_b64})
        result = self.handler.handle(data)

        self.assertEqual(1, mock_flow_v2.call_count)
        self.assertEqual(0, mock_flow_v1.call_count)
