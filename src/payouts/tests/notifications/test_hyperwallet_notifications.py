import json

import responses
from django.conf import settings
from django.urls import reverse

from amuse.tests.helpers import add_zendesk_mock_post_response, build_auth_header
from amuse.tests.test_api.base import AmuseAPITestCase
from payouts.tests.factories import PayeeFactory
from payouts.models import Event


class TestHyperwalletNotificaation(AmuseAPITestCase):
    @responses.activate
    def setUp(self):
        add_zendesk_mock_post_response()
        self.user_notification_payload = {
            "token": "wbh-9e350bf5-854e-4326-9400-611a5c17d8b9",
            "type": "USERS.CREATED",
            "createdOn": "2019-09-13T12:49:43",
            "object": {
                "token": "usr-de305d54-75b4-432b-aac2-eb6b9e546014",
                "status": "CREATED",
                "createdOn": "2019-01-01T16:01:30",
                "clientUserId": "C301245",
                "profileType": "INDIVIDUAL",
                "firstName": "John",
                "lastName": "Smith",
                "email": "johnsmith@yourbrandhere.com",
                "addressLine1": "123 Main Street",
                "city": "New York",
                "stateProvince": "NY",
                "country": "US",
                "postalCode": "10016",
                "language": "en",
                "programToken": "prg-eb305d54-00b4-432b-eac2-ab6b9e123409",
                "verificationStatus": "NOT_REQUIRED",
            },
        }
        self.url = reverse('hyperwallet-notifications-eu')
        self.headers = build_auth_header(
            settings.HYPERWALLET_NOTIFICATION_USER,
            settings.HYPERWALLET_NOTIFICATION_PASSWORD,
        )

    def test_notification_endpoint(self):
        response = self.client.post(
            self.url,
            json.dumps(self.user_notification_payload),
            content_type='application/json',
            **self.headers,
        )
        self.assertEqual(response.status_code, 200)

    def test_auth_failed(self):
        headers = build_auth_header("fake", "fake")
        response = self.client.post(
            self.url,
            json.dumps(self.user_notification_payload),
            content_type='application/json',
            **headers,
        )
        self.assertEqual(response.status_code, 401)

    def test_notification_endpoint_return_400_on_failed(self):
        fake_payload = {"a": 1}
        response = self.client.post(
            self.url,
            json.dumps(fake_payload),
            content_type='application/json',
            **self.headers,
        )
        self.assertEqual(response.status_code, 400)

    def test_full_flow_usr_notification(self):
        payee = PayeeFactory(
            external_id=self.user_notification_payload['object']['token'],
            status='CREATED',
        )
        self.user_notification_payload['object']['status'] = "ACTIVATED"
        self.user_notification_payload['object']['verificationStatus'] = "REQUIRED"
        response = self.client.post(
            self.url,
            json.dumps(self.user_notification_payload),
            content_type='application/json',
            **self.headers,
        )
        self.assertEqual(response.status_code, 200)
        payee.refresh_from_db()
        self.assertEqual(payee.status, "ACTIVATED")
        self.assertEqual(payee.verification_status, 'REQUIRED')
        # Assert Event object is created
        event = Event.objects.get(
            object_id=self.user_notification_payload['object']['token']
        )
        self.assertEqual(event.reason, "HW notification")
