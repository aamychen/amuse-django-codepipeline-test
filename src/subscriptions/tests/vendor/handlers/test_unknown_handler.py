from unittest import mock

from django.test import TestCase

from subscriptions.vendor.google.handlers import HandlerArgs, UnknownNotificationHandler
from subscriptions.vendor.google.enums import ProcessingResult


class TestUnknownHandler(TestCase):
    def setUp(self):
        self.notification_type = 321
        self.event_id = '123x'

    @mock.patch('subscriptions.vendor.google.handlers.unknown_handler.warning')
    def test_log(self, mock_warning):
        processor = UnknownNotificationHandler(self.event_id)

        data = HandlerArgs(
            notification_type=self.notification_type,
            purchase_token='purTkn',
            google_subscription_id='gid',
            purchase={},
        )

        processor.log(data)

        mock_warning.assert_called_once_with(
            self.event_id, f'Unknown notificationType: {self.notification_type}'
        )

    def test_handle(self):
        processor = UnknownNotificationHandler(self.event_id)
        data = HandlerArgs(
            notification_type=self.notification_type,
            purchase_token='purTkn',
            google_subscription_id='gid',
            purchase={},
        )

        result = processor.handle(data)

        self.assertEqual(ProcessingResult.FAIL, result)
