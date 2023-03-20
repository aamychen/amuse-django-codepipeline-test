from unittest import mock

import pytest
from django.test import TestCase

from subscriptions.vendor.google.enums import (
    ProcessingResult,
    SubscriptionNotificationType,
)
from subscriptions.vendor.google.errors import NotificationError, NotificationWarning
from subscriptions.vendor.google.google_play_api import GooglePlayAPI
from subscriptions.vendor.google.handlers import (
    RecoveredNotificationHandler,
    RenewedNotificationHandler,
    CanceledNotificationHandler,
    DeferredNotificationHandler,
    PurchasedNotificationHandler,
    IgnoreNotificationHandler,
    OnHoldNotificationHandler,
    GracePeriodNotificationHandler,
    RestartedNotificationHandler,
    RevokedNotificationHandler,
    PausedNotificationHandler,
    PausedScheduledNotificationHandler,
    UnknownNotificationHandler,
    ExpiredNotificationHandler,
)
from subscriptions.vendor.google.processors.subscription_notification_processor import (
    SubscriptionNotificationProcessor,
    _get_handler,
)


@pytest.mark.parametrize(
    "notification_type,expected_handler_class",
    [
        (SubscriptionNotificationType.RECOVERED, RecoveredNotificationHandler),
        (SubscriptionNotificationType.RENEWED, RenewedNotificationHandler),
        (SubscriptionNotificationType.CANCELED, CanceledNotificationHandler),
        (SubscriptionNotificationType.PURCHASED, PurchasedNotificationHandler),
        (SubscriptionNotificationType.ON_HOLD, OnHoldNotificationHandler),
        (SubscriptionNotificationType.IN_GRACE_PERIOD, GracePeriodNotificationHandler),
        (SubscriptionNotificationType.RESTARTED, RestartedNotificationHandler),
        (
            SubscriptionNotificationType.PRICE_CHANGE_CONFIRMED,
            IgnoreNotificationHandler,
        ),
        (SubscriptionNotificationType.DEFERRED, DeferredNotificationHandler),
        (SubscriptionNotificationType.PAUSED, PausedNotificationHandler),
        (
            SubscriptionNotificationType.PAUSE_SCHEDULE_CHANGED,
            PausedScheduledNotificationHandler,
        ),
        (SubscriptionNotificationType.REVOKED, RevokedNotificationHandler),
        (SubscriptionNotificationType.EXPIRED, ExpiredNotificationHandler),
        (2983, UnknownNotificationHandler),
    ],
)
def test_get_notification_processor(notification_type, expected_handler_class):
    actual = _get_handler('123', notification_type)
    assert isinstance(actual, expected_handler_class)


class TestSubscriptionProcessor(TestCase):
    def setUp(self):
        self.event_id = '123abc'
        self.payload = {
            'subscriptionNotification': {
                'notificationType': 8764,
                'purchaseToken': 'tokenXYZ',
                'subscriptionId': 'sub123',
            }
        }
        self.purchase = {'item': 'value'}
        self.processor = SubscriptionNotificationProcessor(self.payload)

    @mock.patch(
        'subscriptions.vendor.google.processors.subscription_notification_processor.info'
    )
    @mock.patch.object(UnknownNotificationHandler, 'handle')
    @mock.patch.object(UnknownNotificationHandler, 'log')
    @mock.patch.object(GooglePlayAPI, 'verify_purchase_token')
    def test_process(self, mock_verify, mock_log, mock_handler, mock_info):
        mock_verify.return_value = self.purchase
        mock_handler.return_value = ProcessingResult.FAIL
        notification_type = self.payload['subscriptionNotification']['notificationType']

        result = self.processor.process(self.event_id)

        mock_info.assert_called_once_with(
            self.event_id, f'Purchase {str(self.purchase)}'
        )
        mock_log.assert_called_once()
        mock_handler.assert_called_once()
        self.assertEqual(ProcessingResult.FAIL, result)

    @mock.patch.object(GooglePlayAPI, 'verify_purchase_token')
    def test_process_fails_if_unable_to_verify_purchase_token(self, mock_verify):
        mock_verify.return_value = None

        notification_type = self.payload['subscriptionNotification']['notificationType']

        result = self.processor.process(self.event_id)
        self.assertEqual(ProcessingResult.FAIL, result)

    @mock.patch(
        'subscriptions.vendor.google.processors.subscription_notification_processor.warning'
    )
    @mock.patch.object(UnknownNotificationHandler, 'handle')
    @mock.patch.object(GooglePlayAPI, 'verify_purchase_token')
    def test_process_write_warning_log(self, mock_verify, mock_handler, mock_warning):
        mock_verify.return_value = self.purchase
        mock_handler.side_effect = NotificationWarning()
        notification_type = self.payload['subscriptionNotification']['notificationType']

        result = self.processor.process(self.event_id)
        self.assertEqual(ProcessingResult.FAIL, result)
        mock_warning.assert_called_once()

    @mock.patch(
        'subscriptions.vendor.google.processors.subscription_notification_processor.warning'
    )
    @mock.patch.object(UnknownNotificationHandler, 'handle')
    @mock.patch.object(GooglePlayAPI, 'verify_purchase_token')
    def test_process_write_warning_log(self, mock_verify, mock_handler, mock_warning):
        mock_verify.return_value = self.purchase
        mock_handler.side_effect = NotificationError()
        notification_type = self.payload['subscriptionNotification']['notificationType']

        result = self.processor.process(self.event_id)

        self.assertEqual(ProcessingResult.FAIL, result)
        mock_warning.assert_called_once()
