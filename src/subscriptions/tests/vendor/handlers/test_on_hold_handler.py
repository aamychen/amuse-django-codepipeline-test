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
from subscriptions.vendor.google.errors import SubscriptionNotFoundError
from subscriptions.vendor.google.handlers import HandlerArgs, OnHoldNotificationHandler


class TestOnHoldHandler(TestCase):
    @responses.activate
    @mock.patch('amuse.tasks.zendesk_create_or_update_user')
    def setUp(self, _):
        self.notification_type = int(SubscriptionNotificationType.ON_HOLD)
        self.event_id = '123x'
        self.purchase_token = 'purchaseToken123'
        self.google_product_id = 'google_yearly'
        self.order_id = 'order123'

        self.handler = OnHoldNotificationHandler(self.event_id)

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
                'countryCode': 'KL',
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
    def test_raise_an_error_if_subscription_does_not_exist(self, _):
        expiry_date = make_aware(datetime(2000, 10, 20))
        data = self.create_args(
            {
                'orderId': self.order_id,
                'expiryTimeMillis': expiry_date.timestamp() * 1000,
            }
        )
        with pytest.raises(SubscriptionNotFoundError):
            self.handler.handle(data)


class TestGetSubscription(TestCase):
    @responses.activate
    @mock.patch('amuse.tasks.zendesk_create_or_update_user')
    def setUp(self, _):
        self.notification_type = int(SubscriptionNotificationType.EXPIRED)
        self.event_id = '123x'
        self.purchase_token = 'purchaseToken123'
        self.google_product_id = 'google_yearly'
        self.order_id = 'order123'

        self.handler = OnHoldNotificationHandler(self.event_id)

        self.user = UserFactory()
        self.country = CountryFactory(code='SE')
        self.currency = CurrencyFactory(code='SEK')
        self.payment_method = PaymentMethodFactory(
            external_recurring_id=self.purchase_token, method='GOOGL', user=self.user
        )
        self.plan = SubscriptionPlanFactory(google_product_id=self.google_product_id)

    def test_get_active_first(self):
        id = 129
        statuses = [
            Subscription.STATUS_EXPIRED,
            Subscription.STATUS_ACTIVE,
            Subscription.STATUS_GRACE_PERIOD,
        ]

        subs = [
            SubscriptionFactory(
                id=id + i,
                status=status,
                user=self.user,
                provider=Subscription.PROVIDER_GOOGLE,
                payment_method=self.payment_method,
            )
            for i, status in enumerate(statuses)
        ]

        data = HandlerArgs(
            self.notification_type, self.purchase_token, self.google_product_id, None
        )

        sub = self.handler.get_subscription(None, data)

        self.assertEqual(subs[1].id, sub.id)
        self.assertEqual(Subscription.STATUS_ACTIVE, sub.status)


class TestComparator(TestCase):
    @responses.activate
    @mock.patch('amuse.tasks.zendesk_create_or_update_user')
    def setUp(self, _):
        self.notification_type = int(SubscriptionNotificationType.EXPIRED)
        self.event_id = '123x'
        self.purchase_token = 'purchaseToken123'
        self.google_product_id = 'google_yearly'
        self.order_id = 'order123'

        self.handler = OnHoldNotificationHandler(self.event_id)

        self.user = UserFactory()
        self.country = CountryFactory(code='SE')
        self.currency = CurrencyFactory(code='SEK')
        self.payment_method = PaymentMethodFactory(
            external_recurring_id=self.purchase_token, method='GOOGL', user=self.user
        )
        self.plan = SubscriptionPlanFactory(google_product_id=self.google_product_id)

    def create_subscriptions(self, start_id, statuses):
        subs = [
            SubscriptionFactory(
                id=start_id + i,
                status=status,
                user=self.user,
                provider=Subscription.PROVIDER_GOOGLE,
                payment_method=self.payment_method,
            )
            for i, status in enumerate(statuses)
        ]
        return subs
