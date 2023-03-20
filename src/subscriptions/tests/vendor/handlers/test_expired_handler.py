from datetime import datetime, timedelta
from unittest import mock

import pytest
import responses
from django.test import TestCase
from django.utils.timezone import make_aware

from countries.tests.factories import CountryFactory, CurrencyFactory
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
from subscriptions.vendor.google.errors import SubscriptionCannotExpire
from subscriptions.vendor.google.handlers import HandlerArgs, ExpiredNotificationHandler


class TestExpiredHandler(TestCase):
    @responses.activate
    @mock.patch('amuse.tasks.zendesk_create_or_update_user')
    def setUp(self, _):
        self.notification_type = int(SubscriptionNotificationType.EXPIRED)
        self.event_id = '123x'
        self.purchase_token = 'purchaseToken123'
        self.google_product_id = 'google_yearly'
        self.order_id = 'order123'

        self.handler = ExpiredNotificationHandler(self.event_id)

        self.user = UserFactory()
        self.payment_method = PaymentMethodFactory(
            external_recurring_id=self.purchase_token, method='GOOGL', user=self.user
        )
        self.country = CountryFactory(code='SE')
        self.currency = CurrencyFactory(code='SEK')
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
            country=self.country,
            currency=self.currency,
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
    def test_expire_subscription(self, _):
        self.create_subscription_and_payment(
            Subscription.STATUS_GRACE_PERIOD, datetime.now()
        )

        handler = ExpiredNotificationHandler(self.event_id)

        expiry_date = make_aware(datetime(2000, 10, 20))
        data = self.create_args(
            {
                'orderId': self.order_id,
                'expiryTimeMillis': expiry_date.timestamp() * 1000,
            }
        )
        result = handler.handle(data)

        self.assertEqual(ProcessingResult.SUCCESS, result)

        self.subscription.refresh_from_db()
        self.assertEqual(Subscription.STATUS_EXPIRED, self.subscription.status)
        self.assertIsNone(self.subscription.grace_period_until)
        self.assertEqual(expiry_date.date(), self.subscription.valid_until)

    @responses.activate
    @mock.patch('amuse.tasks.zendesk_create_or_update_user')
    def test_already_expired_subscription(self, _):
        self.create_subscription_and_payment(Subscription.STATUS_EXPIRED, None)

        expiry_date = make_aware(datetime.now() + timedelta(days=3))

        handler = ExpiredNotificationHandler(self.event_id)
        data = self.create_args(
            {
                'orderId': self.order_id,
                'expiryTimeMillis': expiry_date.timestamp() * 1000,
            }
        )
        result = handler.handle(data)

        self.assertEqual(ProcessingResult.SUCCESS, result)

        self.subscription.refresh_from_db()
        self.assertEqual(Subscription.STATUS_EXPIRED, self.subscription.status)

        self.payment.refresh_from_db()
        self.assertAlmostEqual(
            expiry_date, self.payment.paid_until, delta=timedelta(seconds=2)
        )

    @responses.activate
    @mock.patch('amuse.tasks.zendesk_create_or_update_user')
    def test_raise_an_error_for_subscription_that_cannot_be_expired(self, _):
        self.create_subscription_and_payment(Subscription.STATUS_CREATED, None)

        data = self.create_args({'orderId': self.order_id})
        with pytest.raises(SubscriptionCannotExpire):
            self.handler.handle(data)

    @responses.activate
    @mock.patch('amuse.tasks.zendesk_create_or_update_user')
    def test_recreate_payment(self, _):
        self.create_subscription_and_payment(Subscription.STATUS_EXPIRED, None)

        handler = ExpiredNotificationHandler(self.event_id)
        expiry_date = make_aware(datetime(2000, 10, 20))
        new_order_id = 'NEW_ORDER_ID'
        data = self.create_args(
            {
                'orderId': new_order_id,
                'countryCode': 'SE',
                'priceCurrencyCode': 'SEK',
                'expiryTimeMillis': expiry_date.timestamp() * 1000,
                'paymentState': 1,
            }
        )
        result = handler.handle(data)

        self.assertEqual(ProcessingResult.SUCCESS, result)

        self.subscription.refresh_from_db()
        self.assertEqual(Subscription.STATUS_EXPIRED, self.subscription.status)

        payments = list(
            PaymentTransaction.objects.filter(
                user=self.user, subscription=self.subscription
            )
        )
        self.assertEqual(2, len(payments))

        orders = [
            payments[0].external_transaction_id,
            payments[1].external_transaction_id,
        ]
        self.assertIn(self.order_id, orders)
        self.assertIn(new_order_id, orders)
