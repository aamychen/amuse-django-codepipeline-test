import json
from unittest.mock import patch

import responses
from django.conf import settings
from django.test import TestCase, override_settings
from amuse.tests.helpers import (
    ZENDESK_MOCK_API_URL_TOKEN,
)

from amuse.tests.helpers import add_zendesk_mock_post_response
from payouts.notifications.hw_trm_notification_handler import (
    HWTransferMethodNotificationHandler,
)
from payouts.tests.factories import TransferMethodFactory
from payouts.models import Event


@override_settings(**ZENDESK_MOCK_API_URL_TOKEN)
class TestHyperwalletTrmNotificationHander(TestCase):
    @responses.activate
    def setUp(self):
        add_zendesk_mock_post_response()
        self.payload = {
            "token": "wbh-fed1665a-9a7d-40a0-a243-40d7aef4a87d",
            "type": "USERS.BANK_ACCOUNTS.CREATED",
            "createdOn": "2021-07-15T08:45:57.251",
            "object": {
                "token": "trm-68e46348-75d8-48fd-b0dc-467b087a02c8",
                "type": "WIRE_ACCOUNT",
                "status": "ACTIVATED",
                "verificationStatus": "NOT_REQUIRED",
                "createdOn": "2021-07-15T08:45:57",
                "transferMethodCountry": "BA",
                "transferMethodCurrency": "USD",
                "bankName": "RAIFFEISEN BANK D.D. BOSNA I HERCEGOVINA",
                "bankId": "RZBABA2S",
                "bankAccountId": "123456789012345678901234",
                "branchAddressLine1": "ZMAJA OD BOSNE BB",
                "branchAddressLine2": "",
                "branchCity": "SARAJEVO",
                "branchStateProvince": "",
                "branchCountry": "BA",
                "branchPostalCode": "71000",
                "userToken": "usr-b55fb39d-07d1-43c3-a33b-80a2a716599f",
                "profileType": "INDIVIDUAL",
                "firstName": "User",
                "lastName": "Artistless",
                "dateOfBirth": "1996-06-09",
                "addressLine1": "fsfsf",
                "city": "Sarajevo",
                "stateProvince": "dsfs",
                "country": "BA",
                "postalCode": "71000",
            },
        }
        self.trm = TransferMethodFactory(
            external_id=self.payload["object"]["token"], status="CREATED"
        )

    @responses.activate
    def test_success_case(self):
        handler = HWTransferMethodNotificationHandler(payload=self.payload)
        status = handler.handle()
        self.trm.refresh_from_db()
        self.assertTrue(status['is_success'])
        self.assertEqual(self.trm.status, self.payload['object']['status'])
        # Assert event is recoded in Event table
        event = Event.objects.get(
            object_id=self.payload['object']['token'],
        )
        self.assertEqual(event.reason, "HW notification")
        self.assertEqual(event.payload, self.payload)

    @patch('payouts.notifications.hw_trm_notification_handler.logger')
    def test_ignore_CREATED_notification(self, mock_fnc):
        self.payload['object']['status'] = "CREATED"
        handler = HWTransferMethodNotificationHandler(payload=self.payload)
        status = handler.handle()
        self.assertEqual(status['is_success'], True)
        mock_fnc.info.assert_called_once_with(
            "HW trm notification handler skipping CREATED notification"
        )

    @patch('payouts.notifications.hw_trm_notification_handler.logger')
    def test_no_trm_found(self, mock_fnc):
        self.payload['object']['token'] = "trm-does-not-exist-in-db"
        handler = HWTransferMethodNotificationHandler(payload=self.payload)
        status = handler.handle()
        self.assertEqual(status['is_success'], False)
        mock_fnc.warning.assert_called_once_with(
            f"HW trm notification handler FAILED error=TransferMethod matching query does not exist. payload {self.payload}"
        )
