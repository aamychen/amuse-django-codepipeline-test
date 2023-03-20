from datetime import datetime, timedelta
from unittest import mock

import pytest
import responses
from django.test import TestCase
from django.utils.timezone import make_aware

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
from subscriptions.vendor.google.errors import SubscriptionCannotCancel
from subscriptions.vendor.google.handlers import (
    HandlerArgs,
    CanceledNotificationHandler,
)


class TestCanceledHandler(TestCase):
    @responses.activate
    @mock.patch('amuse.tasks.zendesk_create_or_update_user')
    def setUp(self, _):
        self.notification_type = int(SubscriptionNotificationType.EXPIRED)
        self.event_id = '123x'
        self.purchase_token = 'purchaseToken123'
        self.google_product_id = 'google_yearly'
        self.order_id = 'order123'

        self.handler = CanceledNotificationHandler(self.event_id)

        self.user = UserFactory()
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
    @mock.patch(
        'subscriptions.vendor.google.handlers.canceled_handler.subscription_canceled'
    )
    def test_cancel_subscription(self, mock_sub_canceled, _):
        self.create_subscription_and_payment(Subscription.STATUS_ACTIVE, None)

        future_date = make_aware(datetime.now() + timedelta(days=3))
        payload = {
            'orderId': self.order_id,
            'expiryTimeMillis': future_date.timestamp() * 1000,
            'cancelReason': 0,
        }
        data = self.create_args(payload)
        result = self.handler.handle(data)

        self.assertEqual(ProcessingResult.SUCCESS, result)

        self.subscription.refresh_from_db()
        self.assertEqual(Subscription.STATUS_ACTIVE, self.subscription.status)
        self.assertIsNotNone(self.subscription.valid_until)
        self.assertEqual(future_date.date(), self.subscription.valid_until)
        mock_sub_canceled.assert_called_once_with(self.subscription)

        self.payment.refresh_from_db()
        self.assertEqual(payload, self.payment.external_payment_response)

    @responses.activate
    @mock.patch('amuse.tasks.zendesk_create_or_update_user')
    @mock.patch(
        'subscriptions.vendor.google.handlers.canceled_handler.subscription_canceled'
    )
    def test_cancel_immediately(self, mock_sub_canceled, _):
        self.create_subscription_and_payment(Subscription.STATUS_ACTIVE, None)

        past_date = make_aware(datetime.now() - timedelta(days=3))
        payload = {
            'orderId': self.order_id,
            'expiryTimeMillis': past_date.timestamp() * 1000,
            'cancelReason': 1,
        }
        data = self.create_args(payload)

        result = self.handler.handle(data)

        self.assertEqual(ProcessingResult.SUCCESS, result)

        self.subscription.refresh_from_db()
        self.assertEqual(Subscription.STATUS_EXPIRED, self.subscription.status)
        self.assertIsNotNone(self.subscription.valid_until)
        self.assertEqual(past_date.date(), self.subscription.valid_until)
        mock_sub_canceled.assert_called_once_with(self.subscription)

        self.payment.refresh_from_db()
        self.assertEqual(payload, self.payment.external_payment_response)

    @responses.activate
    @mock.patch('amuse.tasks.zendesk_create_or_update_user')
    @mock.patch(
        'subscriptions.vendor.google.handlers.canceled_handler.subscription_canceled'
    )
    def test_cancel_immediately_expired_subscription(self, mock_sub_canceled, _):
        self.create_subscription_and_payment(Subscription.STATUS_EXPIRED, None)

        past_date = make_aware(datetime.now() - timedelta(days=3))
        data = self.create_args(
            {'orderId': self.order_id, 'expiryTimeMillis': past_date.timestamp() * 1000}
        )
        result = self.handler.handle(data)

        self.assertEqual(ProcessingResult.SUCCESS, result)
        self.assertEqual(0, mock_sub_canceled.call_count)

    @responses.activate
    @mock.patch('amuse.tasks.zendesk_create_or_update_user')
    def test_raise_an_error_if_cannot_cancel_subscription(self, _):
        self.create_subscription_and_payment(Subscription.STATUS_CREATED, None)
        future_date = make_aware(datetime.now() + timedelta(days=3))

        data = self.create_args(
            {
                'orderId': self.order_id,
                'expiryTimeMillis': future_date.timestamp() * 1000,
            }
        )
        with pytest.raises(SubscriptionCannotCancel):
            self.handler.handle(data)
