from unittest import mock

from django.test import TestCase

from subscriptions.vendor.google.enums import ProcessingResult
from subscriptions.vendor.google.processors import (
    OneTimeNotificationProcessor,
    UnknownNotificationProcessor,
    TestNotificationProcessor,
)


class BaseProcessor(TestCase):
    def setUp(self):
        self.event_id = '123abc'
        self.payload = {
            'subscriptionNotification': '',
            'notificationType': '',
            'purchaseToken': 123,
            'subscriptionId': 123,
        }


class TestUnknownProcessor(BaseProcessor):
    def setUp(self):
        super(TestUnknownProcessor, self).setUp()
        self.processor = UnknownNotificationProcessor(self.payload)

    @mock.patch(
        'subscriptions.vendor.google.processors.unknown_notification_processor.info'
    )
    def test_process(self, mock_info):
        actual = self.processor.process(self.event_id)
        self.assertEqual(ProcessingResult.FAIL, actual)
        mock_info.assert_called_once_with(
            self.event_id,
            f"Received a Unknown Realtime Notification. Not supported. {self.payload}",
        )


class TestOneTimePurchaseProcessor(BaseProcessor):
    def setUp(self):
        super(TestOneTimePurchaseProcessor, self).setUp()
        self.processor = OneTimeNotificationProcessor(self.payload)

    @mock.patch(
        'subscriptions.vendor.google.processors.purchase_notification_processor.info'
    )
    def test_process(self, mock_info):
        actual = self.processor.process(self.event_id)
        self.assertEqual(ProcessingResult.FAIL, actual)
        mock_info.assert_called_once_with(
            self.event_id,
            f'Received a One-Time-Purchase Realtime Notification. Not supported. {str(self.payload)}',
        )


class TestTestNotificationProcessor(BaseProcessor):
    def setUp(self):
        super(TestTestNotificationProcessor, self).setUp()
        self.processor = TestNotificationProcessor(self.payload)

    @mock.patch(
        'subscriptions.vendor.google.processors.test_notification_processor.info'
    )
    def test_process(self, mock_info):
        actual = self.processor.process(self.event_id)
        self.assertEqual(ProcessingResult.SUCCESS, actual)
        mock_info.assert_called_once_with(
            self.event_id,
            f'Received a Test Realtime Developer Notification. {str(self.payload)}',
        )
