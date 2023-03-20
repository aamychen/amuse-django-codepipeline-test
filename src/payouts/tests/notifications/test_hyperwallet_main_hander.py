import json
from unittest.mock import patch

import responses
from django.conf import settings
from django.test import TestCase

from amuse.tests.helpers import add_zendesk_mock_post_response
from payouts.notifications.hw_notification_main_handler import (
    HyperWalletNotificationHandler,
)


class TestHyperwalletNotificationHander(TestCase):
    @responses.activate
    def setUp(self):
        add_zendesk_mock_post_response()
        self.payload = {
            "token": "wbh-7e8e37d9-bb0e-492f-b86f-b228e1bf287b",
            "type": "PAYMENTS.UPDATED.STATUS.PENDING_TRANSACTION_VERIFICATION",
            "createdOn": "2021-07-13T13:19:54.439",
            "object": {
                "token": "pmt-ec291a98-58e8-4494-9cf5-1668be1b4934",
                "status": "PENDING_TRANSACTION_VERIFICATION",
                "createdOn": "2021-07-13T13:19:53",
                "amount": "2500.00",
                "currency": "USD",
                "clientPaymentId": "13",
                "purpose": "OTHER",
                "expiresOn": "2022-01-09T13:19:53",
                "destinationToken": "trm-99d0770c-0379-4289-ac04-c62342e0d85d",
                "programToken": "prg-2157a14c-6c0c-4a5e-83d9-6b6911453af8",
                "foreignExchanges": [
                    {
                        "sourceCurrency": "USD",
                        "sourceAmount": "2,500.00",
                        "destinationCurrency": "EUR",
                        "destinationAmount": "2,009.50",
                        "rate": "0.803800",
                    }
                ],
            },
        }
        self.main_hander = HyperWalletNotificationHandler(payload=self.payload)

    def test_payload_validator_valid(self):
        assert self.main_hander._is_payload_valid()

    def test_payload_validator_invalid_payload(self):
        invalid_payload = {"a": 1, "b": 2}
        handler = HyperWalletNotificationHandler(payload=invalid_payload)
        assert not handler._is_payload_valid()
        status = handler.process_notification()
        self.assertFalse(status['is_success'])
        self.assertEqual(status['reason'], "Invalid payload")

    @patch(
        'payouts.notifications.hw_payment_notification_handler.HWPaymentNotificationHandler.handle'
    )
    def test_payment_handler_called(self, mock_func):
        self.main_hander.process_notification()
        mock_func.assert_called_once()

    @patch(
        'payouts.notifications.hw_trm_notification_handler.HWTransferMethodNotificationHandler.handle'
    )
    def test_trm_handler_called(self, mock_func):
        self.payload['object']['token'] = "trm-ec291a98-58e8-4494-9cf5-1668be1b4934"
        self.main_hander.process_notification()
        mock_func.assert_called_once()

    @patch(
        'payouts.notifications.hw_user_notification_handler.HWUserNotificationHandler.handle'
    )
    def test_user_handler_called(self, mock_func):
        self.payload['object']['token'] = "usr-ec291a98-58e8-4494-9cf5-1668be1b4934"
        self.main_hander.process_notification()
        mock_func.assert_called_once()

    @patch('payouts.notifications.hw_notification_main_handler.logger.warning')
    def test_unknown_token_logged(self, mock_func):
        self.payload['object']['token'] = "xxx-ec291a98-58e8-4494-9cf5-1668be1b4934"
        status = self.main_hander.process_notification()
        self.assertFalse(status['is_success'])
        self.assertEqual(status['reason'], "UNKNOWN_TOKEN_TYPE")
        mock_func.assert_called_once()
