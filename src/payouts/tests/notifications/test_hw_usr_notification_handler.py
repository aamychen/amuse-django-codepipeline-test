import json
from unittest.mock import patch

import responses
from django.conf import settings
from django.test import TestCase, override_settings
from amuse.tests.helpers import (
    ZENDESK_MOCK_API_URL_TOKEN,
)

from amuse.tests.helpers import add_zendesk_mock_post_response
from payouts.notifications.hw_user_notification_handler import HWUserNotificationHandler
from payouts.tests.factories import PayeeFactory
from payouts.models import Event


@override_settings(**ZENDESK_MOCK_API_URL_TOKEN)
class TestHyperwalletUserNotificationHander(TestCase):
    @responses.activate
    def setUp(self):
        add_zendesk_mock_post_response()
        self.payload = {
            "token": "wbh-417988e7-7e06-42d4-bed6-e65000b330fc",
            "type": "USERS.UPDATED.STATUS.PRE_ACTIVATED",
            "createdOn": "2021-07-15T09:38:40.764",
            "object": {
                "token": "usr-2e9ec45a-20dc-410b-9ed9-49ae7bebc333",
                "status": "PRE_ACTIVATED",
                "verificationStatus": "NOT_REQUIRED",
                "createdOn": "2021-07-15T09:38:40",
                "clientUserId": "142328",
                "profileType": "INDIVIDUAL",
                "firstName": "Bxhdsnk",
                "lastName": "Jfcc",
                "dateOfBirth": "1980-01-01",
                "email": "test+summer013@amuse.io",
                "addressLine1": "add",
                "city": "dsdas",
                "stateProvince": "ste",
                "country": "SE",
                "postalCode": "32323",
                "language": "en",
                "timeZone": "GMT",
                "programToken": "prg-2157a14c-6c0c-4a5e-83d9-6b6911453af8",
            },
        }
        self.payee = PayeeFactory(
            external_id=self.payload["object"]["token"], status="CREATED"
        )

    @responses.activate
    def test_success_case(self):
        handler = HWUserNotificationHandler(payload=self.payload)
        status = handler.handle()
        self.payee.refresh_from_db()
        self.assertTrue(status['is_success'])
        self.assertEqual(self.payee.status, self.payload['object']['status'])
        self.assertEqual(
            self.payee.verification_status, self.payload['object']['verificationStatus']
        )
        # Assert event is recoded in Event table
        event = Event.objects.get(
            object_id="usr-2e9ec45a-20dc-410b-9ed9-49ae7bebc333",
        )
        self.assertEqual(event.reason, "HW notification")
        self.assertEqual(event.payload, self.payload)

    @patch('payouts.notifications.hw_user_notification_handler.logger')
    def test_ignore_CREATED_notification(self, mock_fnc):
        self.payload['object']['status'] = "CREATED"
        handler = HWUserNotificationHandler(payload=self.payload)
        status = handler.handle()
        self.assertEqual(status['is_success'], True)
        mock_fnc.info.assert_called_once_with(
            "HW User notification handler skipping CREATED notification"
        )

    @patch('payouts.notifications.hw_user_notification_handler.logger')
    def test_no_payee_found(self, mock_fnc):
        self.payload['object']['token'] = "user-does-not-exist-in-db"
        handler = HWUserNotificationHandler(payload=self.payload)
        status = handler.handle()
        self.assertEqual(status['is_success'], False)
        mock_fnc.warning.assert_called_once_with(
            f"HW User notification handler FAILED error=Payee matching query does not exist. payload {self.payload}"
        )
