from unittest import mock

from django.test import TestCase

from subscriptions.vendor.google.handlers import HandlerArgs, IgnoreNotificationHandler
from subscriptions.vendor.google.enums import (
    ProcessingResult,
    SubscriptionNotificationType,
)


class TestIgnoreHandler(TestCase):
    def setUp(self):
        self.notification_type = SubscriptionNotificationType.PURCHASED
        self.event_id = 'event123'

    @mock.patch('subscriptions.vendor.google.handlers.ignore_handler.info')
    def test_log(self, mock_info):
        processor = IgnoreNotificationHandler(self.event_id)

        data = HandlerArgs(
            notification_type=self.notification_type,
            purchase_token='purTkn',
            google_subscription_id='gid',
            purchase={},
        )

        processor.log(data)

        mock_info.assert_called_once_with(
            self.event_id,
            f'Ignored notificationType: {SubscriptionNotificationType(self.notification_type).name}',
        )

    def test_handle(self):
        processor = IgnoreNotificationHandler(self.event_id)
        data = HandlerArgs(
            notification_type=self.notification_type,
            purchase_token='purTkn',
            google_subscription_id='gid',
            purchase={},
        )

        result = processor.handle(data)

        self.assertEqual(ProcessingResult.SUCCESS, result)
