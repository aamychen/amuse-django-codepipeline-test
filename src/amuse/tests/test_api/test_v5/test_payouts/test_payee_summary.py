from unittest.mock import patch

import responses
from django.urls import reverse
from hyperwallet.models import User, TransferMethod
from hyperwallet.exceptions import HyperwalletAPIException

from amuse.tests.helpers import add_zendesk_mock_post_response
from amuse.tests.test_api.base import AmuseAPITestCase, API_V5_ACCEPT_VALUE
from users.tests.factories import UserFactory
from payouts.tests.factories import ProviderFactory, PayeeFactory, TransferMethodFactory


class TestTransferMethodApi(AmuseAPITestCase):
    @responses.activate
    def setUp(self):
        add_zendesk_mock_post_response()
        self.user = UserFactory(country="US", email='test@example.com')
        self.payee_defaults = {
            'clientUserId': str(self.user.id),
            'country': self.user.country,
            'dateOfBirth': "1980-01-01",
            'email': self.user.email,
            'firstName': self.user.first_name,
            'lastName': self.user.last_name,
            'profileType': "INDIVIDUAL",
            'programToken': "prg-19d7ef5e-e01e-43bc-b271-79eef1062832",
            'status': "PRE_ACTIVATED",
            'token': "usr-3c0840da-fbf4-464d-9bcb-a16018de66b7",
            'verificationStatus': "NOT_REQUIRED",
            'profileType': "INDIVIDUAL",
        }
        self.trm_defaults = {
            "count": 1,
            "limit": 10,
            "data": [
                {
                    "token": "trm-56b976c5-26b2-42fa-87cf-14b3366673c6",
                    "type": "BANK_ACCOUNT",
                    "status": "ACTIVATED",
                    "transferMethodCountry": "US",
                    "transferMethodCurrency": "USD",
                    "userToken": "usr-3c0840da-fbf4-464d-9bcb-a16018de66b7",
                    "branchId": "026009593",
                    "bankAccountId": "****5206",
                    "bankAccountPurpose": "CHECKING",
                    "profileType": "INDIVIDUAL",
                    "firstName": "John",
                    "lastName": "Smith",
                    "dateOfBirth": "1980-01-01",
                    "addressLine1": "123 Main Street",
                    "city": "New York",
                    "stateProvince": "NY",
                    "country": "US",
                    "postalCode": "10016",
                }
            ],
        }
        self.provide = ProviderFactory(
            name="HW_PROGRAM_WORLD",
            external_id="prg-19d7ef5e-e01e-43bc-b271-79eef1062832",
        )
        self.payee = PayeeFactory(
            user=self.user, external_id="usr-3c0840da-fbf4-464d-9bcb-a16018de66b7"
        )
        self.url = reverse("payee_summary")

        self.client.force_authenticate(self.user)
        self.client.credentials(HTTP_ACCEPT=API_V5_ACCEPT_VALUE)

    @patch("hyperwallet.Api.getUser")
    @patch("hyperwallet.Api.listTransferMethods")
    def test_get_payee_summary(self, mocked_list_trms, mocked_get_user):
        mocked_get_user.return_value = User(self.payee_defaults)
        mocked_list_trms.return_value = TransferMethod(self.trm_defaults)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data['is_success'])
        self.assertIsNotNone(response.data['data']['user_profile'])
        self.assertIsNotNone(response.data['data']['trms'])

    @patch("hyperwallet.Api.getUser")
    @patch("hyperwallet.Api.listTransferMethods")
    def test_get_payee_summary_failed(self, mocked_list_trms, mocked_get_user):
        mocked_get_user.side_effect = HyperwalletAPIException(
            {
                "errors": [
                    {
                        "message": "Error message",
                        "fieldName": "clientUserId",
                        "code": "ERROR  CODE",
                        "relatedResources": [
                            "usr-3c0840da-fbf4-464d-9bcb-a16018de66b7"
                        ],
                    }
                ]
            }
        )
        mocked_list_trms.return_value = TransferMethod(self.trm_defaults)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 404)
        self.assertFalse(response.data['is_success'])
        self.assertTrue(response.data['reason'] is not None)

    @patch("hyperwallet.Api.getUser")
    @patch("hyperwallet.Api.listTransferMethods")
    def test_get_payee_summary_filter(self, mocked_list_trms, mocked_get_user):
        trm_defaults = {
            "count": 2,
            "limit": 10,
            "data": [
                {
                    "token": "trm-56b976c5-26b2-42fa-87cf-14b3366673c6",
                    "type": "BANK_ACCOUNT",
                    "status": "ACTIVATED",
                    "transferMethodCountry": "US",
                    "transferMethodCurrency": "USD",
                    "userToken": "usr-3c0840da-fbf4-464d-9bcb-a16018de66b7",
                },
                {
                    "token": "trm-56b976c5-26b2-42fa-87cf-14b3366673c7",
                    "type": "BANK_ACCOUNT",
                    "status": "ACTIVATED",
                    "transferMethodCountry": "US",
                    "transferMethodCurrency": "USD",
                    "userToken": "usr-3c0840da-fbf4-464d-9bcb-a16018de66b7",
                },
            ],
        }

        mocked_get_user.return_value = User(self.payee_defaults)
        mocked_list_trms.return_value = TransferMethod(trm_defaults)
        # Create inactive trm that will be filtered
        TransferMethodFactory(
            external_id="trm-56b976c5-26b2-42fa-87cf-14b3366673c7",
            active=False,
            payee=self.payee,
        )
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data['is_success'])
        self.assertIsNotNone(response.data['data']['user_profile'])
        self.assertIsNotNone(response.data['data']['trms'])
        self.assertEqual(response.data['data']['trms']['count'], 1)
        self.assertEqual(len(response.data['data']['trms']['data']), 1)
        self.assertEqual(
            response.data['data']['trms']['data'][0]['token'],
            "trm-56b976c5-26b2-42fa-87cf-14b3366673c6",
        )
