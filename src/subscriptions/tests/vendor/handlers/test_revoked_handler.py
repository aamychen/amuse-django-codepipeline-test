from datetime import datetime
from unittest import mock

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
from subscriptions.vendor.google.handlers import HandlerArgs, RevokedNotificationHandler


class TestRevokedHandler(TestCase):
    @responses.activate
    @mock.patch('amuse.tasks.zendesk_create_or_update_user')
    def setUp(self, _):
        self.notification_type = int(SubscriptionNotificationType.REVOKED)
        self.event_id = '123x'
        self.purchase_token = 'purchaseToken123'
        self.google_product_id = 'google_yearly'
        self.order_id = 'order123'
        self.order_id1 = 'order123..1'

        self.handler = RevokedNotificationHandler(self.event_id)

        self.user = UserFactory()
        self.country = CountryFactory(code='SE')
        self.currency = CurrencyFactory(code='SEK')
        self.payment_method = PaymentMethodFactory(
            external_recurring_id=self.purchase_token, method='GOOGL', user=self.user
        )
        self.plan = SubscriptionPlanFactory(google_product_id=self.google_product_id)

    def create_subscription_and_payment(self, status):
        valid_from = make_aware(datetime.now() - timedelta(days=10))
        valid_until = make_aware(datetime.now() + timedelta(days=20))

        self.subscription = SubscriptionFactory(
            user=self.user,
            status=status,
            provider=Subscription.PROVIDER_GOOGLE,
            payment_method=self.payment_method,
            plan=self.plan,
            valid_from=valid_from,
        )
        self.payment = PaymentTransactionFactory(
            external_transaction_id=self.order_id,
            plan=self.plan,
            subscription=self.subscription,
            user=self.user,
            paid_until=valid_until,
            status=PaymentTransaction.STATUS_APPROVED,
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
    def test_revoke_subscription_with_single_payment(self, _):
        for status in [Subscription.STATUS_ACTIVE, Subscription.STATUS_EXPIRED]:
            with self.subTest(msg=f'Test revoke {status} subscription'):
                self.create_subscription_and_payment(status)

                expiry_date = make_aware(datetime.now())
                data = self.create_args(
                    {
                        'orderId': self.order_id,
                        'expiryTimeMillis': expiry_date.timestamp() * 1000,
                        'purchaseToken': self.purchase_token,
                        'countryCode': 'SE',
                        'priceCurrencyCode': 'SEK',
                    }
                )
                result = self.handler.handle(data)

                self.assertEqual(ProcessingResult.SUCCESS, result)

                self.subscription.refresh_from_db()
                self.assertEqual(Subscription.STATUS_EXPIRED, self.subscription.status)
                self.assertIsNotNone(self.subscription.valid_until)
                self.assertEqual(
                    self.subscription.valid_from, self.subscription.valid_until
                )

                self.assertTrue(
                    PaymentTransaction.objects.filter(
                        external_transaction_id=self.order_id,
                        status=PaymentTransaction.STATUS_CANCELED,
                    ).exists()
                )

    @responses.activate
    @mock.patch('amuse.tasks.zendesk_create_or_update_user')
    def test_revoke_subscription_with_multiple_payments(self, _):
        for status in [Subscription.STATUS_ACTIVE, Subscription.STATUS_EXPIRED]:
            with self.subTest(
                msg=f"Test revoke with multiple payments for {status} subscription"
            ):
                self.create_subscription_and_payment(status)

                paid_until = self.payment.paid_until + timedelta(days=30)
                payment2 = PaymentTransactionFactory(
                    external_transaction_id=self.order_id1,
                    plan=self.plan,
                    subscription=self.subscription,
                    user=self.user,
                    paid_until=paid_until,
                )

                expiry_date = make_aware(datetime.now())
                data = self.create_args(
                    {
                        'orderId': self.order_id1,
                        'expiryTimeMillis': expiry_date.timestamp() * 1000,
                        'purchaseToken': self.purchase_token,
                        'countryCode': 'SE',
                        'priceCurrencyCode': 'SEK',
                    }
                )
                result = self.handler.handle(data)

                self.assertEqual(ProcessingResult.SUCCESS, result)

                self.subscription.refresh_from_db()
                self.assertEqual(Subscription.STATUS_EXPIRED, self.subscription.status)
                self.assertIsNotNone(self.subscription.valid_until)
                self.assertEqual(
                    self.payment.paid_until.date(), self.subscription.valid_until
                )

                self.assertTrue(
                    PaymentTransaction.objects.filter(
                        external_transaction_id=self.order_id,
                        status=PaymentTransaction.STATUS_APPROVED,
                    ).exists()
                )
                self.assertTrue(
                    PaymentTransaction.objects.filter(
                        external_transaction_id=self.order_id1,
                        status=PaymentTransaction.STATUS_CANCELED,
                    ).exists()
                )
