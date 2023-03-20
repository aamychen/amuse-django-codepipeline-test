from datetime import datetime
from decimal import Decimal
from unittest import mock

import pytest
import responses
from django.test import TestCase
from django.utils.timezone import make_aware, timedelta

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
from subscriptions.vendor.google.errors import PaymentTransactionAlreadyExistsError
from subscriptions.vendor.google.google_play_api import GooglePlayAPI
from subscriptions.vendor.google.handlers import HandlerArgs, RenewedNotificationHandler
from subscriptions.vendor.google.handlers.renewed_handler import Downgrade


class TestGraceHandler(TestCase):
    @responses.activate
    @mock.patch('amuse.tasks.zendesk_create_or_update_user')
    def setUp(self, _):
        self.notification_type = int(SubscriptionNotificationType.EXPIRED)
        self.event_id = '123x'
        self.purchase_token = 'purchaseToken123'
        self.google_product_id = 'google_yearly'
        self.order_id = 'order123'

        self.handler = RenewedNotificationHandler(self.event_id)

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
    def test_renew_with_new_payment(self, _):
        self.create_subscription_and_payment(Subscription.STATUS_ACTIVE, None)

        future_date = make_aware(datetime.now() + timedelta(days=3))
        data = self.create_args(
            {
                'orderId': 'NEW_ORDER_ID',
                'expiryTimeMillis': future_date.timestamp() * 1000,
                'purchaseToken': self.purchase_token,
                'countryCode': 'SE',
                'priceCurrencyCode': 'SEK',
                'paymentState': 0,
            }
        )
        result = self.handler.handle(data)

        self.assertEqual(ProcessingResult.SUCCESS, result)

        self.subscription.refresh_from_db()
        self.assertEqual(Subscription.STATUS_ACTIVE, self.subscription.status)
        self.assertIsNone(self.subscription.grace_period_until)
        self.assertIsNone(self.subscription.valid_until)

        self.assertTrue(
            PaymentTransaction.objects.filter(
                external_transaction_id='NEW_ORDER_ID'
            ).exists()
        )

    @responses.activate
    @mock.patch('amuse.tasks.zendesk_create_or_update_user')
    @mock.patch(
        'subscriptions.vendor.google.handlers.renewed_handler.subscription_successful_renewal'
    )
    def test_renew_with_existing_payment(self, mock_sub_renewed, _):
        self.create_subscription_and_payment(Subscription.STATUS_GRACE_PERIOD, None)

        future_date = make_aware(datetime.now() + timedelta(days=3))
        data = self.create_args(
            {
                'orderId': self.order_id,
                'expiryTimeMillis': future_date.timestamp() * 1000,
                'purchaseToken': self.purchase_token,
                'countryCode': 'SE',
                'priceCurrencyCode': 'SEK',
                'paymentState': 0,
                'priceAmountMicros': '1230000',
            }
        )
        result = self.handler.handle(data)

        self.assertEqual(ProcessingResult.SUCCESS, result)

        self.subscription.refresh_from_db()
        self.assertEqual(Subscription.STATUS_ACTIVE, self.subscription.status)
        self.assertIsNone(self.subscription.grace_period_until)
        self.assertIsNone(self.subscription.valid_until)
        mock_sub_renewed.assert_called_once_with(
            self.subscription, Decimal('1.23'), 'SE'
        )

    @responses.activate
    @mock.patch('amuse.tasks.zendesk_create_or_update_user')
    @mock.patch(
        'subscriptions.vendor.google.handlers.renewed_handler.subscription_successful_renewal'
    )
    def test_new_subscription(self, mock_sub_renewed, _):
        self.create_subscription_and_payment(Subscription.STATUS_EXPIRED, None)
        future_date = make_aware(datetime.now() + timedelta(days=3))
        data = self.create_args(
            {
                'orderId': 'NEW_ORDER_ID',
                'expiryTimeMillis': future_date.timestamp() * 1000,
                'purchaseToken': self.purchase_token,
                'countryCode': 'SE',
                'priceCurrencyCode': 'SEK',
                'paymentState': 0,
                'priceAmountMicros': '1230000',
            }
        )
        result = self.handler.handle(data)

        self.assertEqual(ProcessingResult.SUCCESS, result)

        self.subscription.refresh_from_db()
        self.assertEqual(Subscription.STATUS_EXPIRED, self.subscription.status)

        new_subscription = Subscription.objects.filter(
            user=self.user, status=Subscription.STATUS_ACTIVE
        ).first()

        self.assertIsNotNone(new_subscription)
        mock_sub_renewed.assert_called_once_with(
            new_subscription, Decimal('1.23'), 'SE'
        )

    @responses.activate
    @mock.patch('amuse.tasks.zendesk_create_or_update_user')
    def test_raise_an_error_if_cannot_create_new_subscription(self, _):
        self.create_subscription_and_payment(Subscription.STATUS_EXPIRED, None)
        expiry_date = make_aware(datetime(2000, 10, 20))
        data = self.create_args(
            {
                'orderId': self.order_id,
                'expiryTimeMillis': expiry_date.timestamp() * 1000,
                'purchaseToken': self.purchase_token,
                'countryCode': 'SE',
                'priceCurrencyCode': 'SEK',
                'paymentState': 0,
            }
        )
        with pytest.raises(PaymentTransactionAlreadyExistsError):
            self.handler.handle(data)

    @responses.activate
    @mock.patch('amuse.tasks.zendesk_create_or_update_user')
    def test_expire_subscription(self, _):
        self.create_subscription_and_payment(Subscription.STATUS_ACTIVE, None)

        past_date = make_aware(datetime.now() - timedelta(days=3))
        data = self.create_args(
            {
                'orderId': 'NEW_ORDER_ID',
                'expiryTimeMillis': past_date.timestamp() * 1000,
                'purchaseToken': self.purchase_token,
                'countryCode': 'SE',
                'priceCurrencyCode': 'SEK',
                'paymentState': 0,
            }
        )
        result = self.handler.handle(data)

        self.assertEqual(ProcessingResult.SUCCESS, result)

        self.subscription.refresh_from_db()
        self.assertEqual(Subscription.STATUS_EXPIRED, self.subscription.status)

    @responses.activate
    @mock.patch('amuse.tasks.zendesk_create_or_update_user')
    @mock.patch.object(Downgrade, 'handle', return_value=ProcessingResult.SUCCESS)
    def test_is_downgrade(self, mock_downgrade, _):
        self.create_subscription_and_payment(Subscription.STATUS_ACTIVE, None)

        past_date = make_aware(datetime.now() - timedelta(days=3))
        data = self.create_args({})

        # Case #1
        actual = self.handler.is_downgrade_flow(data)
        self.assertFalse(actual, 'should be False if linkedPurchaseToken not provided')

        # Case #2
        data = self.create_args({'linkedPurchaseToken': 'linkedPurchaseToken'})
        actual = self.handler.is_downgrade_flow(data)
        self.assertFalse(
            actual, 'should be False if linkedPurchaseToken exists, and payment exists'
        )

        # Case #3
        data = self.create_args({'linkedPurchaseToken': 'linkedPurchaseToken'})
        data.purchase_token = 'newPurchaseToken'
        actual = self.handler.is_downgrade_flow(data)
        self.assertTrue(
            actual,
            'should be True if linkedPurchaseToken exists, but payment does not exist',
        )

    @responses.activate
    @mock.patch('amuse.tasks.zendesk_create_or_update_user')
    @mock.patch.object(
        RenewedNotificationHandler, 'is_downgrade_flow', return_value=True
    )
    @mock.patch.object(Downgrade, 'handle', return_value=ProcessingResult.SUCCESS)
    def test_run_downgrade(self, mock_is_downgrade_flow, mock_downgrade, _):
        data = self.create_args({})
        self.handler.handle(data)

        mock_downgrade.assert_called_once_with(data)

    @responses.activate
    @mock.patch('amuse.tasks.zendesk_create_or_update_user')
    @mock.patch(
        'subscriptions.vendor.google.handlers.renewed_handler.subscription_successful_renewal'
    )
    @mock.patch(
        'subscriptions.vendor.google.handlers.renewed_handler.subscription_changed'
    )
    @mock.patch.object(GooglePlayAPI, 'acknowledge', return_value=None)
    def test_downgrade(self, mock_ack, mock_sub_changed, mock_sub_renewed, _):
        self.create_subscription_and_payment(Subscription.STATUS_ACTIVE, None)

        expiry_date = make_aware(datetime.now() + timedelta(days=3))
        data = self.create_args(
            {
                'orderId': 'NEW_ORDER_ID',
                'expiryTimeMillis': expiry_date.timestamp() * 1000,
                'linkedPurchaseToken': self.purchase_token,
                'countryCode': 'SE',
                'priceCurrencyCode': 'SEK',
                'paymentState': 1,
                'priceAmountMicros': '1230000',
            }
        )
        data.purchase_token = 'newPurchaseToken'
        result = Downgrade('123').handle(data)

        self.assertEqual(ProcessingResult.SUCCESS, result)

        self.subscription.refresh_from_db()
        self.assertEqual(Subscription.STATUS_EXPIRED, self.subscription.status)

        new_subscription = Subscription.objects.filter(
            payment_method__external_recurring_id=data.purchase_token,
            provider=Subscription.PROVIDER_GOOGLE,
            status__in=[Subscription.STATUS_ACTIVE],
        ).first()

        self.assertIsNotNone(new_subscription)
        mock_ack.assert_called_once()
        mock_sub_changed.assert_called_once_with(
            new_subscription,
            self.subscription.plan,
            new_subscription.plan,
            None,
            None,
            'SE',
        )
        mock_sub_renewed.assert_called_once_with(
            new_subscription, Decimal('1.23'), 'SE'
        )
