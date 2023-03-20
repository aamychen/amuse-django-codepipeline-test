from datetime import datetime
from unittest import mock

import responses
from django.test import TestCase
from django.utils.timezone import make_aware, timedelta

from countries.tests.factories import CountryFactory, CurrencyFactory
from payments.tests.factories import PaymentMethodFactory, PaymentTransactionFactory
from subscriptions.models import Subscription
from subscriptions.tests.factories import (
    SubscriptionFactory,
    SubscriptionPlanFactory,
    UserFactory,
)
from subscriptions.vendor.google import PurchaseSubscription
from subscriptions.vendor.google.enums import (
    ProcessingResult,
    SubscriptionNotificationType,
)
from subscriptions.vendor.google.handlers import (
    HandlerArgs,
    DeferredNotificationHandler,
)


class TestDeferredHandler(TestCase):
    @responses.activate
    @mock.patch('amuse.tasks.zendesk_create_or_update_user')
    def setUp(self, _):
        self.notification_type = int(SubscriptionNotificationType.DEFERRED)
        self.event_id = '123x'
        self.purchase_token = 'purchaseToken123'
        self.google_product_id = 'google_monthly'
        self.order_id = 'order123'

        self.handler = DeferredNotificationHandler(self.event_id)

        self.user = UserFactory()
        self.country = CountryFactory(code='SE')
        self.currency = CurrencyFactory(code='SEK')
        self.payment_method = PaymentMethodFactory(
            external_recurring_id=self.purchase_token, method='GOOGL', user=self.user
        )
        self.plan = SubscriptionPlanFactory(google_product_id=self.google_product_id)

    def create_subscription_and_payment(self, status):
        self.subscription = SubscriptionFactory(
            user=self.user,
            status=status,
            provider=Subscription.PROVIDER_GOOGLE,
            payment_method=self.payment_method,
            plan=self.plan,
            grace_period_until=None,
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
    def test_extend_transaction(self, _):
        self.create_subscription_and_payment(Subscription.STATUS_ACTIVE)

        expiry_date = make_aware(datetime.now() + timedelta(days=10))
        data = self.create_args(
            {
                "expiryTimeMillis": expiry_date.timestamp() * 1000,
                "orderId": self.order_id,
            }
        )
        result = self.handler.handle(data)

        self.assertEqual(ProcessingResult.SUCCESS, result)

        # ensure subscription is not created
        self.assertEqual(1, Subscription.objects.count())
        self.payment.refresh_from_db()
        self.assertEqual(expiry_date.date(), self.payment.paid_until.date())
