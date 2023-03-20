from datetime import datetime
from unittest import mock

import pytest
import responses
from django.test import TestCase
from django.utils.timezone import make_aware

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
from subscriptions.vendor.google.errors import SubscriptionCannotExpire
from subscriptions.vendor.google.handlers import HandlerArgs, PausedNotificationHandler


class TestPausedHandler(TestCase):
    @responses.activate
    @mock.patch('amuse.tasks.zendesk_create_or_update_user')
    def setUp(self, _):
        self.notification_type = int(SubscriptionNotificationType.EXPIRED)
        self.event_id = '123x'
        self.purchase_token = 'purchaseToken123'
        self.google_product_id = 'google_yearly'
        self.order_id = 'order123'

        self.handler = PausedNotificationHandler(self.event_id)

        self.user = UserFactory()
        self.country = CountryFactory(code='SE')
        self.currency = CurrencyFactory(code='SEK')
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
    def test_expire_subscription(self, _):
        self.create_subscription_and_payment(Subscription.STATUS_ACTIVE, None)

        expiry_date = make_aware(datetime(2000, 10, 20))
        data = self.create_args(
            {
                'orderId': self.order_id,
                'expiryTimeMillis': expiry_date.timestamp() * 1000,
            }
        )
        result = self.handler.handle(data)

        self.assertEqual(ProcessingResult.SUCCESS, result)

        self.subscription.refresh_from_db()
        self.assertEqual(Subscription.STATUS_EXPIRED, self.subscription.status)
        self.assertIsNone(self.subscription.grace_period_until)
        self.assertEqual(expiry_date.date(), self.subscription.valid_until)

    @responses.activate
    @mock.patch('amuse.tasks.zendesk_create_or_update_user')
    def test_already_expired_subscription(self, _):
        expiry_date = make_aware(datetime(2000, 10, 20))
        self.create_subscription_and_payment(Subscription.STATUS_EXPIRED, expiry_date)

        data = self.create_args(
            {
                'orderId': self.order_id,
                'expiryTimeMillis': expiry_date.timestamp() * 1000,
            }
        )
        result = self.handler.handle(data)

        self.assertEqual(ProcessingResult.SUCCESS, result)

        self.subscription.refresh_from_db()
        self.assertEqual(Subscription.STATUS_EXPIRED, self.subscription.status)
        self.assertIsNone(self.subscription.grace_period_until)
        self.assertEqual(expiry_date.date(), self.subscription.valid_until)

    @responses.activate
    @mock.patch('amuse.tasks.zendesk_create_or_update_user')
    def test_raise_an_error_if_cannot_expire_subscription(self, _):
        self.create_subscription_and_payment(Subscription.STATUS_ERROR, None)
        expiry_date = make_aware(datetime(2000, 10, 20))
        data = self.create_args(
            {
                'orderId': self.order_id,
                'expiryTimeMillis': expiry_date.timestamp() * 1000,
            }
        )
        with pytest.raises(SubscriptionCannotExpire):
            self.handler.handle(data)
