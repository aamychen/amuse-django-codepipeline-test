import base64
import json
from unittest import mock

import pytest
from django.test import TestCase
from django.utils import timezone

from subscriptions.vendor.google.enums import ProcessingResult
from subscriptions.vendor.google.notifications import (
    GoogleBillingNotificationProcessor,
    _get_notification_processor,
)
from subscriptions.vendor.google.processors import (
    OneTimeNotificationProcessor,
    SubscriptionNotificationProcessor,
    TestNotificationProcessor,
    UnknownNotificationProcessor,
)


@pytest.mark.parametrize(
    "payload,expected",
    [
        ({'subscriptionNotification': {}}, SubscriptionNotificationProcessor),
        ({'testNotification': {}}, TestNotificationProcessor),
        ({'oneTimePurchaseNotification': {}}, OneTimeNotificationProcessor),
        ({}, UnknownNotificationProcessor),
    ],
)
def test_get_notification_processor(payload, expected):
    actual = _get_notification_processor(payload)
    assert isinstance(actual, expected)


class TestDecodeDataMethod(TestCase):
    def setUp(self):
        self.event_id = '123abc'
        self.decode_func = GoogleBillingNotificationProcessor(
            self.event_id
        )._decode_payload

    @mock.patch('subscriptions.vendor.google.notifications.info')
    def test_return_none_if_message_missing(self, mock_info):
        payload = {}
        actual = self.decode_func(payload)
        self.assertIsNone(actual)
        mock_info.assert_called_once_with(
            self.event_id, "Invalid payload. 'Message' missing"
        )

    @mock.patch('subscriptions.vendor.google.notifications.info')
    def test_return_none_if_message_data_missing(self, mock_info):
        payload = {'message': {}}
        actual = self.decode_func(payload)
        self.assertIsNone(actual)
        mock_info.assert_called_once_with(
            self.event_id, "Invalid payload. Message 'data' missing"
        )

    @mock.patch('subscriptions.vendor.google.notifications.warning')
    def test_return_none_if_unable_to_decode_message_data(self, mock_warning):
        payload = {'message': {'data': 'abc-invalid'}}
        actual = self.decode_func(payload)
        self.assertIsNone(actual)
        mock_warning.assert_called_once_with(self.event_id, 'Incorrect padding')

    @mock.patch('subscriptions.vendor.google.notifications.info')
    def test_success(self, mock_info):
        input_data = {'a': 'aa', 'b': 'bb'}
        input_data_encoded = base64.standard_b64encode(
            json.dumps(input_data).encode('utf-8')
        ).decode('utf-8')
        payload = {'message': {'data': input_data_encoded}}

        actual = self.decode_func(payload)
        self.assertIsNotNone(actual)
        mock_info.assert_called_once_with(
            self.event_id, f'Decoded data: {str(input_data)}'
        )


class TestProcessMethod(TestCase):
    def setUp(self):
        self.event_id = '123abc'
        self.processor = GoogleBillingNotificationProcessor(self.event_id)

    @mock.patch.object(SubscriptionNotificationProcessor, 'process')
    def test_success_subscription(self, mock_process):
        input_data = {'subscriptionNotification': 'aa'}
        input_data_encoded = base64.standard_b64encode(
            json.dumps(input_data).encode('utf-8')
        ).decode('utf-8')
        payload = {
            'message': {
                'data': input_data_encoded,
                'message_id': str(timezone.now().timestamp()),
            }
        }

        response = self.processor.process(payload)
        mock_process.assert_called_once_with(self.event_id)

    def test_return_fail_if_decode_fails(self):
        response = self.processor.process({})
        self.assertEqual(response, ProcessingResult.FAIL)
