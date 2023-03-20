from datetime import datetime, timedelta
from decimal import Decimal
from functools import cmp_to_key
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
    PriceCardFactory,
    SubscriptionFactory,
    SubscriptionPlanFactory,
    UserFactory,
)
from subscriptions.vendor.google import PurchaseSubscription
from subscriptions.vendor.google.enums import SubscriptionNotificationType
from subscriptions.vendor.google.errors import (
    SubscriptionsMultipleActiveError,
    SubscriptionsMultipleActivePurchaseTokenError,
    PaymentMethodNotFoundError,
    PaymentTransactionNotFoundError,
    SubscriptionPlanNotFoundError,
)
from subscriptions.vendor.google.handlers import IgnoreNotificationHandler
from subscriptions.vendor.google.handlers.abstract_handler import (
    subscription_comparator,
)
from subscriptions.vendor.google.handlers.containers import HandlerArgs


class TestGetActiveSubscriptionsByUser(TestCase):
    @responses.activate
    @mock.patch('amuse.tasks.zendesk_create_or_update_user')
    def setUp(self, _):
        self.user = UserFactory()
        self.handler = IgnoreNotificationHandler('event123')

    def test_return_single_subscription(self):
        subscription = SubscriptionFactory(
            user=self.user,
            status=Subscription.STATUS_ACTIVE,
            provider=Subscription.PROVIDER_GOOGLE,
        )

        actual = self.handler.get_active_subscription_by_user(self.user.id)
        self.assertEqual(actual, subscription)

    def test_return_none(self):
        actual = self.handler.get_active_subscription_by_user(self.user.id)
        self.assertIsNone(actual)

    def test_raise_exception_for_multiple_active_subscriptions(self):
        for i in range(0, 2):
            SubscriptionFactory(
                user=self.user,
                status=Subscription.STATUS_ACTIVE,
                provider=Subscription.PROVIDER_GOOGLE,
            )

        with pytest.raises(SubscriptionsMultipleActiveError):
            self.handler.get_active_subscription_by_user(self.user.id)


class TestGetActiveSubscriptionsByToken(TestCase):
    @responses.activate
    @mock.patch('amuse.tasks.zendesk_create_or_update_user')
    def setUp(self, _):
        self.purchase_token = 'purchaseToken123'
        self.user = UserFactory()
        self.payment_method = PaymentMethodFactory(
            external_recurring_id=self.purchase_token,
            method='GOOGL',
            summary='9000',
            user=self.user,
        )
        self.handler = IgnoreNotificationHandler('event123')

    def test_return_single_subscription(self):
        subscription = SubscriptionFactory(
            user=self.user,
            status=Subscription.STATUS_ACTIVE,
            provider=Subscription.PROVIDER_GOOGLE,
            payment_method=self.payment_method,
        )

        actual = self.handler.get_active_subscription_by_token(self.purchase_token)
        self.assertEqual(subscription, actual)

    def test_return_none(self):
        actual = self.handler.get_active_subscription_by_token(self.user.id)
        self.assertIsNone(actual)

    def test_raise_exception_for_multiple_active_subscriptions(self):
        for i in range(0, 2):
            SubscriptionFactory(
                user=self.user,
                status=Subscription.STATUS_ACTIVE,
                provider=Subscription.PROVIDER_GOOGLE,
                payment_method=self.payment_method,
            )

        with pytest.raises(SubscriptionsMultipleActivePurchaseTokenError):
            self.handler.get_active_subscription_by_token(self.purchase_token)


class TestGetPaymentMethod(TestCase):
    @responses.activate
    @mock.patch('amuse.tasks.zendesk_create_or_update_user')
    def setUp(self, _):
        self.purchase_token = 'purchaseToken123'
        self.data = HandlerArgs(1, self.purchase_token, 'googleSubId', None)
        self.handler = IgnoreNotificationHandler('event123')

    @responses.activate
    @mock.patch('amuse.tasks.zendesk_create_or_update_user')
    def test_return_payment_method(self, _):
        payment_method = PaymentMethodFactory(external_recurring_id=self.purchase_token)

        actual = self.handler.get_payment_method(self.data)
        self.assertEqual(payment_method, actual)

    def test_raise_exception_for_none_payment_method(self):
        with pytest.raises(PaymentMethodNotFoundError):
            self.handler.get_payment_method(self.data)


class TestGetPaymentTransaction(TestCase):
    def setUp(self):
        self.order_id = 'orderId123'
        self.data = HandlerArgs(
            1,
            'purchaseToken',
            'googleSubId',
            PurchaseSubscription(**{'orderId': self.order_id}),
        )
        self.handler = IgnoreNotificationHandler('event123')

    @responses.activate
    @mock.patch('amuse.tasks.zendesk_create_or_update_user')
    def test_return_payment_transaction(self, _):
        expected = PaymentTransactionFactory(external_transaction_id=self.order_id)

        actual = self.handler.get_payment_transaction(self.data)
        self.assertEqual(expected, actual)

    def test_raise_exception_for_none_payment_method(self):
        with pytest.raises(PaymentTransactionNotFoundError):
            self.handler.get_payment_transaction(self.data)

    def test_do_not_raise_exception_for_none_payment_method(self):
        actual = self.handler.get_payment_transaction(self.data, raise_exception=False)
        self.assertIsNone(actual)


class TestGetPlan(TestCase):
    def setUp(self):
        self.google_product_id = 'yearly_sub'
        self.data = HandlerArgs(1, 'purchaseToken', self.google_product_id, None)
        self.handler = IgnoreNotificationHandler('event123')

    @responses.activate
    @mock.patch('amuse.tasks.zendesk_create_or_update_user')
    def test_return_plan(self, _):
        expected = SubscriptionPlanFactory(google_product_id=self.google_product_id)

        actual = self.handler.get_plan(self.data)
        self.assertEqual(expected, actual)

    def test_raise_exception_for_none_plan(self):
        with pytest.raises(SubscriptionPlanNotFoundError):
            self.handler.get_plan(self.data)


class TestGetPrice(TestCase):
    @responses.activate
    def test_get_price(self):
        test_cases = [
            {
                'description': 'test non_acknowledged purchase',
                'expected': '0.0',
                'payload': {'priceAmountMicros': '1990000', 'acknowledgementState': 0},
            },
            {
                'description': 'test non_acknowledged purchase (string payload)',
                'expected': '0.0',
                'payload': {
                    'priceAmountMicros': '1990000',
                    'acknowledgementState': '0',
                },
            },
            {
                'description': 'test acknowledged purchase',
                'expected': '1.99',
                'payload': {'priceAmountMicros': '1990000', 'acknowledgementState': 1},
            },
            {
                'description': 'test acknowledged purchase (string payload)',
                'expected': '1.99',
                'payload': {
                    'priceAmountMicros': '1990000',
                    'acknowledgementState': '1',
                },
            },
            {
                'description': 'test purchase with unknown acknowledged state',
                'expected': '0.0',
                'payload': {'priceAmountMicros': '1990000'},
            },
        ]

        for tc in test_cases:
            with self.subTest(msg=f"{tc['description']}"):
                purchase = PurchaseSubscription(**tc['payload'])
                expected = Decimal(tc['expected'])

                data = HandlerArgs(1, 'xy', 'x', purchase)
                handler = IgnoreNotificationHandler('event123')
                actual = handler.get_price(data)
                self.assertEqual(expected, actual)


class TestPaymentTransactionNew(TestCase):
    @responses.activate
    @mock.patch('amuse.tasks.zendesk_create_or_update_user')
    def setUp(self, _):
        tomorrow = datetime.now() + timedelta(days=1)

        self.purchase_token = 'purchaseToken123'
        self.google_product_id = 'yearly_sub'
        self.order_id = 'google-order-id-123'
        purchase = PurchaseSubscription(
            **{
                'expiryTimeMillis': datetime.timestamp(tomorrow) * 1000,
                'countryCode': 'SE',
                'priceCurrencyCode': 'SEK',
                'paymentState': 1,
                'orderId': self.order_id,
            }
        )

        self.data = HandlerArgs(
            1, self.purchase_token, self.google_product_id, purchase
        )
        self.handler = IgnoreNotificationHandler('event123')

        self.country = CountryFactory(code='SE')
        self.currency = CurrencyFactory(code='SEK')
        self.plan = SubscriptionPlanFactory(
            period=12, create_card=False, google_product_id=self.google_product_id
        )
        self.payment_method = PaymentMethodFactory(
            external_recurring_id=self.purchase_token
        )

        self.subscription = SubscriptionFactory(
            status=Subscription.STATUS_ACTIVE,
            provider=Subscription.PROVIDER_GOOGLE,
            payment_method=self.payment_method,
            plan=self.plan,
        )
        card = PriceCardFactory(
            price=Decimal("559.00"),
            plan=self.plan,
            currency=self.currency,
            countries=[self.country],
        )

    def test_create_payment_transaction(self):
        payment = self.handler.payment_transaction_new(self.subscription, self.data)
        self.assertIsNotNone(payment)
        self.assertEqual(PaymentTransaction.CATEGORY_RENEWAL, payment.category)
        self.assertEqual(self.order_id, payment.external_transaction_id)


class TestPaymentTransactionUpdate(TestCase):
    @responses.activate
    @mock.patch('amuse.tasks.zendesk_create_or_update_user')
    def setUp(self, _):
        self.handler = IgnoreNotificationHandler('event123')
        self.payment = PaymentTransactionFactory()

    def test_update_payment_transaction(self):
        future_date = make_aware(datetime.now() + timedelta(days=3))
        purchase = PurchaseSubscription(
            **{'paymentState': 1, 'expiryTimeMillis': future_date.timestamp() * 1000}
        )

        data = HandlerArgs(1, 'purchaseToken123', 'googleProductId', purchase)
        self.handler.payment_transaction_update(self.payment, data)

        self.payment.refresh_from_db()
        self.assertEqual(PaymentTransaction.STATUS_APPROVED, self.payment.status)
        self.assertEqual(purchase.payload, self.payment.external_payment_response)


class TestGetHandleableSubscription(TestCase):
    @responses.activate
    @mock.patch('amuse.tasks.zendesk_create_or_update_user')
    def setUp(self, _):
        self.notification_type = int(SubscriptionNotificationType.EXPIRED)
        self.event_id = '123x'
        self.purchase_token = 'purchaseToken123'
        self.google_product_id = 'google_yearly'
        self.order_id = 'order123'

        self.handler = IgnoreNotificationHandler(self.event_id)

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

    def test_active_first(self):
        start_id = 892
        subs = self.create_subscriptions(
            start_id,
            [
                Subscription.STATUS_EXPIRED,
                Subscription.STATUS_ACTIVE,
                Subscription.STATUS_ACTIVE,
                Subscription.STATUS_GRACE_PERIOD,
            ],
        )

        subs.sort(key=cmp_to_key(subscription_comparator))

        self.assertEqual(
            Subscription.STATUS_ACTIVE, subs[0].status, 'active subs on the top'
        )
        self.assertEqual(
            start_id + 2, subs[0].id, 'with greater id should be on the top'
        )

        self.assertEqual(Subscription.STATUS_ACTIVE, subs[1].status)
        self.assertEqual(start_id + 1, subs[1].id)

        self.assertEqual(Subscription.STATUS_GRACE_PERIOD, subs[2].status)
        self.assertEqual(Subscription.STATUS_EXPIRED, subs[3].status)

    def test_compare_by_ids(self):
        start_id = 912
        subs = self.create_subscriptions(
            start_id,
            [
                Subscription.STATUS_ACTIVE,
                Subscription.STATUS_ACTIVE,
                Subscription.STATUS_ACTIVE,
            ],
        )

        subs.sort(key=cmp_to_key(subscription_comparator))

        self.assertEqual(Subscription.STATUS_ACTIVE, subs[0].status)
        self.assertEqual(start_id + 2, subs[0].id)

        self.assertEqual(Subscription.STATUS_ACTIVE, subs[1].status)
        self.assertEqual(start_id + 1, subs[1].id)

        self.assertEqual(Subscription.STATUS_ACTIVE, subs[2].status)
        self.assertEqual(start_id, subs[2].id)
        self.assertEqual(Subscription.STATUS_ACTIVE, subs[2].status)
