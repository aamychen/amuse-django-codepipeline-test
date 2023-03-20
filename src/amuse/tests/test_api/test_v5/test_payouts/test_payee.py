from unittest.mock import patch

import responses
from django.conf import settings
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from hyperwallet.models import AuthenticationToken, User
from hyperwallet.exceptions import HyperwalletAPIException

from amuse.tests.helpers import add_zendesk_mock_post_response
from amuse.tests.test_api.base import AmuseAPITestCase, API_V5_ACCEPT_VALUE
from users.tests.factories import UserFactory
from payouts.tests.factories import ProviderFactory, PayeeFactory
from payouts.models import Payee, Event


class TestPayeeApi(AmuseAPITestCase):
    @responses.activate
    def setUp(self):
        add_zendesk_mock_post_response()
        self.user = UserFactory(
            country="US",
            email='test@example.com',
            phone='+524423439277',
            phone_verified=True,
        )
        self.defaults = {
            'addressLine1': "123 Main Street",
            'city': "New York",
            'clientUserId': str(self.user.id),
            'country': self.user.country,
            'dateOfBirth': "1980-01-01",
            'email': self.user.email,
            'firstName': self.user.first_name,
            'lastName': self.user.last_name,
            'postalCode': "10016",
            'profileType': "INDIVIDUAL",
            'programToken': "prg-19d7ef5e-e01e-43bc-b271-79eef1062832",
            'stateProvince': "NY",
            'status': "PRE_ACTIVATED",
            'token': "usr-3c0840da-fbf4-464d-9bcb-a16018de66b7",
            'verificationStatus': "NOT_REQUIRED",
            'profileType': "INDIVIDUAL",
        }
        self.hw_user = User(self.defaults)
        self.provide = ProviderFactory(
            name="HW_PROGRAM_WORLD",
            external_id="prg-19d7ef5e-e01e-43bc-b271-79eef1062832",
        )
        self.payload = {
            "profile_type": "INDIVIDUAL",
            "dob": "1980-01-01",
            "address": "123 Main Street",
            "city": "New York",
            "state_province": "NY",
            "postal_code": "10016",
        }
        self.client.force_authenticate(self.user)
        self.client.credentials(HTTP_ACCEPT=API_V5_ACCEPT_VALUE)

    @patch("hyperwallet.Api.getAuthenticationToken")
    def test_get_hw_auth_token_success(self, mocked_method):
        mocked_method.return_value = AuthenticationToken(
            {"value": "pGOdbYermGhiON5IFKSnXZd6Zj"}
        )
        PayeeFactory(
            user=self.user, external_id='usr-3c0840da-fbf4-464d-9bcb-a16018de66b7'
        )
        url = reverse("payee_auth_token")
        response = self.client.get(path=url)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data['is_success'])
        self.assertIsNotNone(response.data['data']['value'])

    @patch("hyperwallet.Api.getAuthenticationToken")
    def test_get_hw_auth_token_not_found(self, mocked_method):
        mocked_method.return_value = AuthenticationToken(
            {"value": "pGOdbYermGhiON5IFKSnXZd6Zj"}
        )
        url = reverse("payee_auth_token")
        response = self.client.get(path=url)
        self.assertEqual(response.status_code, 404)
        self.assertFalse(response.data['is_success'])
        self.assertIsNone(response.data['data'])
        self.assertIsNotNone(response.data['reason'])

    @patch("hyperwallet.Api.getAuthenticationToken")
    def test_get_hw_auth_token_api_error(self, mocked_method):
        PayeeFactory(
            user=self.user, external_id='usr-3c0840da-fbf4-464d-9bcb-a16018de66b7'
        )
        mocked_method.side_effect = HyperwalletAPIException(
            {
                "errors": [
                    {
                        "message": "Error message",
                        "fieldName": "",
                        "code": "ERROR_CODE",
                        "relatedResources": [
                            "usr-3c0840da-fbf4-464d-9bcb-a16018de66b7"
                        ],
                    }
                ]
            }
        )
        url = reverse("payee_auth_token")
        response = self.client.get(path=url)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.data['is_success'])
        self.assertIsNone(response.data['data'])
        self.assertIsNotNone(response.data['reason'])

    @patch("hyperwallet.Api.createUser")
    def test_create_hw_user_success(self, mock_method):
        mock_method.return_value = self.hw_user
        url = reverse("payee")
        response = self.client.post(path=url, data=self.payload, format='json')
        self.assertEqual(response.status_code, 201)
        # Assert Event object is created in DB
        event = Event.objects.get(object_id=self.defaults['token'])
        self.assertIsNotNone(event)
        self.assertEqual(event.initiator, "SYSTEM")
        self.assertEqual(event.reason, "API call")
        self.assertEqual(event.payload['token'], self.defaults['token'])

        # Assert Payee object created in DB
        payee = Payee.objects.get(pk=self.user.id)
        self.assertIsNotNone(event)
        self.assertEqual(payee.external_id, self.defaults['token'])
        self.assertEqual(payee.type, Payee.TYPE_INDIVIDUAL)
        self.assertEqual(payee.status, "PRE_ACTIVATED")
        self.assertEqual(payee.verification_status, "NOT_REQUIRED")
        self.assertEqual(payee.provider, self.provide)

    @patch("hyperwallet.Api.createUser")
    def test_create_hw_user_success_optional_fields(self, mock_method):
        mock_method.return_value = self.hw_user
        url = reverse("payee")
        self.payload['address2'] = "Second adress"
        self.payload['middle_name'] = "Middle Name      "
        response = self.client.post(path=url, data=self.payload, format='json')
        self.assertEqual(response.status_code, 201)
        # Assert Event object is created in DB
        event = Event.objects.get(object_id=self.defaults['token'])
        self.assertIsNotNone(event)
        self.assertEqual(event.initiator, "SYSTEM")
        self.assertEqual(event.reason, "API call")
        self.assertEqual(event.payload['token'], self.defaults['token'])

        # Assert Payee object created in DB
        payee = Payee.objects.get(pk=self.user.id)
        self.assertIsNotNone(event)
        self.assertEqual(payee.external_id, self.defaults['token'])
        self.assertEqual(payee.type, Payee.TYPE_INDIVIDUAL)
        self.assertEqual(payee.status, "PRE_ACTIVATED")
        self.assertEqual(payee.verification_status, "NOT_REQUIRED")
        self.assertEqual(payee.provider, self.provide)

    @patch("hyperwallet.Api.createUser")
    def test_create_hw_user_success_government_id(self, mock_method):
        mock_method.return_value = self.hw_user
        url = reverse("payee")
        self.payload['address2'] = "Second adress"
        self.payload['middle_name'] = "Middle Name"
        self.payload['government_id'] = "870908-3456"
        response = self.client.post(path=url, data=self.payload, format='json')
        self.assertEqual(response.status_code, 201)
        # Assert Event object is created in DB
        event = Event.objects.get(object_id=self.defaults['token'])
        self.assertIsNotNone(event)
        self.assertEqual(event.initiator, "SYSTEM")
        self.assertEqual(event.reason, "API call")
        self.assertEqual(event.payload['token'], self.defaults['token'])

        # Assert Payee object created in DB
        payee = Payee.objects.get(pk=self.user.id)
        self.assertIsNotNone(event)
        self.assertEqual(payee.external_id, self.defaults['token'])
        self.assertEqual(payee.type, Payee.TYPE_INDIVIDUAL)
        self.assertEqual(payee.status, "PRE_ACTIVATED")
        self.assertEqual(payee.verification_status, "NOT_REQUIRED")
        self.assertEqual(payee.provider, self.provide)
        self.assertEqual(payee.government_id, self.payload['government_id'])

    @patch("hyperwallet.Api.createUser")
    def test_create_hw_user_failed(self, mock_method):
        mock_method.side_effect = HyperwalletAPIException(
            {
                "errors": [
                    {
                        "message": "Error message",
                        "fieldName": "",
                        "code": "ERROR_CODE",
                        "relatedResources": [
                            "usr-3c0840da-fbf4-464d-9bcb-a16018de66b7"
                        ],
                    }
                ]
            }
        )
        url = reverse("payee")
        response = self.client.post(path=url, data=self.payload, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.data['is_success'])
        self.assertEqual(response.data['reason']['errors'][0]['code'], 'ERROR_CODE')

    def test_get_payee_404(self):
        url = reverse('payee')
        response = self.client.get(url)
        self.assertFalse(response.data['is_success'])
        self.assertEqual(response.status_code, 404)

    def test_get_payee_200(self):
        PayeeFactory(user=self.user)
        url = reverse('payee')
        response = self.client.get(url)
        self.assertTrue(response.data['is_success'])
        self.assertEqual(response.status_code, 200)

    @patch("hyperwallet.Api.updateUser")
    @patch("hyperwallet.Api.createUser")
    def test_update_hw_user_success(self, mock_method, mock_update):
        mock_method.return_value = self.hw_user
        mock_update.return_value = self.hw_user
        # First create hw user first
        url = reverse("payee")
        response = self.client.post(path=url, data=self.payload, format='json')
        self.assertEqual(response.status_code, 201)

        # Test update
        update_payload = {"addressLine2": "4631 Coolidge Street"}
        update_response = self.client.put(path=url, data=update_payload, format='json')
        self.assertEqual(update_response.status_code, 200)

        # Assert Event object is created in DB
        Event.objects.get(object_id=self.defaults['token'], reason="API call UPDATE")

    @patch("hyperwallet.Api.updateUser")
    @patch("hyperwallet.Api.createUser")
    def test_update_hw_user_failed_hw_error(self, mock_method, mock_update):
        mock_method.return_value = self.hw_user
        mock_update.side_effect = HyperwalletAPIException(
            {
                "errors": [
                    {
                        "message": "Error message",
                        "fieldName": "",
                        "code": "ERROR_CODE",
                        "relatedResources": [
                            "usr-3c0840da-fbf4-464d-9bcb-a16018de66b7"
                        ],
                    }
                ]
            }
        )
        # First create hw user first
        url = reverse("payee")
        response = self.client.post(path=url, data=self.payload, format='json')
        self.assertEqual(response.status_code, 201)

        # Test update
        update_payload = {"addressLine2": "4631 Coolidge Street"}
        update_response = self.client.put(path=url, data=update_payload, format='json')
        self.assertEqual(update_response.status_code, 400)
        self.assertFalse(update_response.data['is_success'])
        self.assertIsNotNone(update_response.data['reason'])

    @patch("hyperwallet.Api.updateUser")
    def test_update_hw_user_failed_payee_not_found(self, mock_update):
        mock_update.side_effect = self.hw_user
        url = reverse("payee")
        update_payload = {"addressLine2": "4631 Coolidge Street"}
        update_response = self.client.put(path=url, data=update_payload, format='json')
        self.assertEqual(update_response.status_code, 400)
        self.assertFalse(update_response.data['is_success'])
        self.assertIsNotNone(update_response.data['reason'])

    @patch("hyperwallet.Api.updateUser")
    def test_update_hw_user_failed_invalid_se_government_id(self, mock_update):
        mock_update.side_effect = self.hw_user
        user = UserFactory(
            country="SE",
            email='test2@example.com',
            phone='+524423439277',
            phone_verified=True,
        )
        payee = PayeeFactory(user=user)
        client = self.client
        client.force_authenticate(user)
        client.credentials(HTTP_ACCEPT=API_V5_ACCEPT_VALUE)
        url = reverse("payee")
        update_payload = {
            "addressLine2": "4631 Coolidge Street",
            "government_id": "19850811-1234",
        }
        update_response = client.put(path=url, data=update_payload, format='json')
        self.assertEqual(update_response.status_code, 400)
        self.assertEqual(
            update_response.data.get('government_id')[0], 'government_id is not valid'
        )

    @patch("hyperwallet.Api.updateUser")
    def test_update_hw_user_se_pnr_success(self, mock_update):
        user = UserFactory(
            country="SE",
            email='test3@example.com',
            phone='+524423439277',
            phone_verified=True,
        )
        payee = PayeeFactory(user=user)
        mock_update.return_value = User(
            {
                'addressLine1': "123 Main Street",
                'city': "New York",
                'clientUserId': str(user.id),
                'country': user.country,
                'dateOfBirth': "1980-01-01",
                'email': user.email,
                'firstName': user.first_name,
                'lastName': user.last_name,
                'postalCode': "10016",
                'profileType': "INDIVIDUAL",
                'programToken': "prg-19d7ef5e-e01e-43bc-b271-79eef1062832",
                'stateProvince': "NY",
                'status': "PRE_ACTIVATED",
                'token': payee.external_id,
                'verificationStatus': "NOT_REQUIRED",
                'profileType': "INDIVIDUAL",
            }
        )

        client = self.client
        client.force_authenticate(user)
        client.credentials(HTTP_ACCEPT=API_V5_ACCEPT_VALUE)
        url = reverse("payee")
        update_payload = {
            "addressLine2": "4631 Coolidge Street",
            "government_id": "19850811-1237",
        }
        update_response = client.put(path=url, data=update_payload, format='json')
        self.assertEqual(update_response.status_code, 200)
        self.assertTrue(update_response.data['is_success'])
        payee.refresh_from_db()
        self.assertEqual(payee.government_id, update_payload['government_id'])

    @patch("hyperwallet.Api.createUser")
    def test_create_hw_user_invalid_se_government_id(self, mock_method):
        mock_method.return_value = self.hw_user
        user = UserFactory(
            country="SE",
            email='test3@example.com',
            phone='+524423439277',
            phone_verified=True,
        )
        url = reverse("payee")
        payload = self.payload
        payload['government_id'] = "879908-3456"
        client = self.client
        client.force_authenticate(user)
        client.credentials(HTTP_ACCEPT=API_V5_ACCEPT_VALUE)
        response = client.post(path=url, data=payload, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.data.get('government_id')[0], 'government_id is not valid'
        )
