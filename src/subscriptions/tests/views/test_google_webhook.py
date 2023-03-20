import json
from unittest.mock import patch

import responses
from django.test import TestCase
from django.urls import reverse
from rest_framework import status

from subscriptions.vendor.google.notifications import GoogleBillingNotificationProcessor
from subscriptions.vendor.google.enums import ProcessingResult


class GoogleSubscriptionWebhookViewTestCase(TestCase):
    def setUp(self):
        self.url = reverse('google-subscriptions')
        self.payload = {'field1': 'value1'}

    def _post(self):
        return self.client.post(
            self.url, json.dumps(self.payload), content_type='application/json'
        )

    @responses.activate
    @patch('subscriptions.vendor.google.exception')
    @patch('subscriptions.views.google_webhook.new_eventid', return_value='abc123')
    @patch.object(GoogleBillingNotificationProcessor, 'process', return_value=None)
    def test_return_400_if_processor_returns_none(
        self, mock_processor, mock_eventid, mock_exception
    ):
        response = self._post()

        self.assertEqual(status.HTTP_400_BAD_REQUEST, response.status_code)
        mock_processor.assert_called_once_with(self.payload)
        mock_eventid.assert_called_once()
        self.assertEqual(0, mock_exception.call_count)

    @responses.activate
    @patch('subscriptions.views.google_webhook.warning')
    @patch('subscriptions.views.google_webhook.new_eventid', return_value='abc123')
    @patch.object(
        GoogleBillingNotificationProcessor,
        'process',
        side_effect=Exception('i am sorry'),
    )
    def test_return_500_if_processor_raise_exception(
        self, mock_processor, mock_eventid, mock_warning
    ):
        response = self._post()

        self.assertEqual(status.HTTP_500_INTERNAL_SERVER_ERROR, response.status_code)
        mock_processor.assert_called_once_with(self.payload)
        mock_eventid.assert_called_once()
        mock_warning.assert_called_once_with(
            'abc123', 'PANIC! Unhandled exception: "i am sorry"'
        )

    @responses.activate
    @patch('subscriptions.views.google_webhook.warning')
    @patch('subscriptions.views.google_webhook.new_eventid', return_value='abc123')
    @patch.object(
        GoogleBillingNotificationProcessor,
        'process',
        return_value=ProcessingResult.SUCCESS,
    )
    def test_return_200_if_processor_returns_success(
        self, mock_processor, mock_eventid, mock_warning
    ):
        response = self._post()

        self.assertEqual(status.HTTP_200_OK, response.status_code)
        mock_processor.assert_called_once_with(self.payload)
        mock_eventid.assert_called_once()
        self.assertEqual(0, mock_warning.call_count)
