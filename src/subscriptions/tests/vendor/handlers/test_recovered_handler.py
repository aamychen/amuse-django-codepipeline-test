from datetime import datetime, timedelta
from unittest import mock

import responses
from django.test import TestCase
from django.utils.timezone import make_aware

from countries.tests.factories import CurrencyFactory, CountryFactory
from payments.models import PaymentTransaction
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
    RecoveredNotificationHandler,
)


class TestRecoveredHandler(TestCase):
    @responses.activate
    @mock.patch('amuse.tasks.zendesk_create_or_update_user')
    def setUp(self, _):
        self.notification_type = int(SubscriptionNotificationType.EXPIRED)
        self.event_id = '123x'
        self.purchase_token = 'purchaseToken123'
        self.google_product_id = 'google_yearly'
        self.order_id = 'order123'

        self.handler = RecoveredNotificationHandler(self.event_id)

        self.country = CountryFactory(code='US')
        self.currency = CurrencyFactory(code='USD')

        self.user = UserFactory()
        self.payment_method = PaymentMethodFactory(
            external_recurring_id=self.purchase_token, method='GOOGL', user=self.user
        )
        self.plan = SubscriptionPlanFactory(google_product_id=self.google_product_id)

    def create_subscription_and_payment(self, status, valid_until):
        self.subscription = SubscriptionFactory(
            user=self.user,
            status=status,
            provider=Subscription.PROVIDER_GOOGLE,
            payment_method=self.payment_method,
            plan=self.plan,
            valid_until=valid_until,
            grace_period_until=None,
        )
        self.payment = PaymentTransactionFactory(
            external_transaction_id=self.order_id,
            plan=self.plan,
            subscription=self.subscription,
            user=self.user,
            currency=self.currency,
            country=self.country,
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
    def test_recover_subscription(self, _):
        past_date = make_aware(datetime.now() - timedelta(days=3))
        future_date = make_aware(datetime.now() + timedelta(days=3))
        self.create_subscription_and_payment(
            Subscription.STATUS_EXPIRED, past_date.date()
        )

        new_order_id = (f'{self.order_id}..001',)
        data = self.create_args(
            {
                'orderId': new_order_id,
                'expiryTimeMillis': future_date.timestamp() * 1000,
                'countryCode': self.country.code,
                'priceCurrencyCode': self.currency.code,
                'paymentState': 1,
            }
        )

        self.assertEqual(1, Subscription.objects.filter(user=self.user).count())
        result = self.handler.handle(data)

        self.assertEqual(ProcessingResult.SUCCESS, result)
        self.assertEqual(2, Subscription.objects.filter(user=self.user).count())

        payment = PaymentTransaction.objects.filter(
            external_transaction_id=new_order_id
        ).first()
        self.assertIsNotNone(payment)
        self.assertEqual(PaymentTransaction.STATUS_APPROVED, payment.status)
