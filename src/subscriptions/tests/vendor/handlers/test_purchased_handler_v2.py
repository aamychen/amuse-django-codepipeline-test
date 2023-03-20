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
from subscriptions.vendor.google import PurchaseSubscription, GooglePlayAPI
from subscriptions.vendor.google.enums import (
    ProcessingResult,
    SubscriptionNotificationType,
)
from subscriptions.vendor.google.handlers import HandlerArgs
from subscriptions.vendor.google.handlers.purchased_handler_v2 import (
    PurchasedNotificationHandlerV2,
    Upgrade,
)


class TestPurchaseHandlerV2(TestCase):
    @responses.activate
    @mock.patch('amuse.tasks.zendesk_create_or_update_user')
    def setUp(self, _):
        self.notification_type = int(SubscriptionNotificationType.EXPIRED)
        self.event_id = '123x'
        self.purchase_token = 'purchaseToken123'
        self.google_product_id = 'google_monthly'
        self.order_id = 'order123'

        self.user = UserFactory()
        self.country = CountryFactory(code='SE')
        self.currency = CurrencyFactory(code='SEK')
        self.payment_method = PaymentMethodFactory(
            external_recurring_id=self.purchase_token, method='GOOGL', user=self.user
        )
        self.plan = SubscriptionPlanFactory(google_product_id=self.google_product_id)
        self.handler = PurchasedNotificationHandlerV2(self.event_id, self.user)

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
    @mock.patch.object(GooglePlayAPI, 'verify_purchase_token')
    def test_regular_flow(self, mock_verify, _):
        expiry_date = make_aware(datetime.now() + timedelta(days=3))
        purchase = {
            'expiryTimeMillis': expiry_date.timestamp() * 1000,
            'priceAmountMicros': '1990000',
            'countryCode': self.country.code,
            'priceCurrencyCode': self.currency.code,
            'orderId': 'GOOGLE-TEST-SUB-123',
            'paymentState': 1,
            'autoRenewing': True,
        }
        mock_verify.return_value = purchase
        data = self.create_args(purchase)
        result = self.handler.handle(data)

        self.assertEqual(ProcessingResult.SUCCESS, result)

        # ensure subscription is created
        qs = Subscription.objects.filter(user=self.user)
        self.assertEqual(1, qs.count())
        self.assertEqual(Subscription.STATUS_ACTIVE, qs.all()[0].status)

    @responses.activate
    @mock.patch('amuse.tasks.zendesk_create_or_update_user')
    @mock.patch.object(Upgrade, 'handle', return_value=ProcessingResult.SUCCESS)
    def test_is_upgrade(self, mock_upgrade, _):
        self.create_subscription_and_payment(Subscription.STATUS_ACTIVE, None)

        past_date = make_aware(datetime.now() - timedelta(days=3))
        data = self.create_args({})

        # Case #1
        actual = self.handler.is_upgrade_flow(data)
        self.assertFalse(actual, 'should be False if linkedPurchaseToken not provided')

        # Case #2
        data = self.create_args({'linkedPurchaseToken': 'linkedPurchaseToken'})
        actual = self.handler.is_upgrade_flow(data)
        self.assertFalse(
            actual, 'should be False if linkedPurchaseToken exists, and payment exists'
        )

        # Case #3
        data = self.create_args({'linkedPurchaseToken': 'linkedPurchaseToken'})
        data.purchase_token = 'newPurchaseToken'
        actual = self.handler.is_upgrade_flow(data)
        self.assertTrue(
            actual,
            'should be True if linkedPurchaseToken exists, but payment does not exist',
        )

    @responses.activate
    @mock.patch('amuse.tasks.zendesk_create_or_update_user')
    @mock.patch.object(
        PurchasedNotificationHandlerV2, 'is_upgrade_flow', return_value=True
    )
    @mock.patch.object(Upgrade, 'handle', return_value=ProcessingResult.SUCCESS)
    def test_run_upgrade(self, mock_is_upgrade_flow, mock_upgrade, _):
        data = self.create_args({})
        self.handler.handle(data)

        mock_is_upgrade_flow.assert_called_once_with(data)
        mock_upgrade.assert_called_once_with(data)

    @responses.activate
    @mock.patch('amuse.tasks.zendesk_create_or_update_user')
    @mock.patch(
        'subscriptions.vendor.google.handlers.purchased_handler_v2.subscription_changed'
    )
    def test_upgrade(self, mock_sub_changed, _):
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
            }
        )
        data.purchase_token = 'newPurchaseToken'
        result = Upgrade('123', self.user).handle(data)

        self.assertEqual(ProcessingResult.SUCCESS, result)

        self.subscription.refresh_from_db()
        self.assertEqual(Subscription.STATUS_EXPIRED, self.subscription.status)

        new_subscription = Subscription.objects.filter(
            payment_method__external_recurring_id=data.purchase_token,
            provider=Subscription.PROVIDER_GOOGLE,
            status__in=[Subscription.STATUS_ACTIVE],
        ).first()

        self.assertIsNotNone(new_subscription)
        self.assertEqual(self.subscription.user, new_subscription.user)
        self.assertEqual(Subscription.STATUS_EXPIRED, self.subscription.status)
        mock_sub_changed.assert_called_once_with(
            new_subscription,
            self.subscription.plan,
            new_subscription.plan,
            None,
            None,
            'SE',
        )
