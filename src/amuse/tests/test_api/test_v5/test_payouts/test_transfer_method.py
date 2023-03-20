from unittest.mock import patch

import responses
from django.urls import reverse
from hyperwallet.models import User, TransferMethod
from hyperwallet.exceptions import HyperwalletAPIException

from amuse.tests.helpers import add_zendesk_mock_post_response
from amuse.tests.test_api.base import AmuseAPITestCase, API_V5_ACCEPT_VALUE
from users.tests.factories import UserFactory
from payouts.tests.factories import ProviderFactory, PayeeFactory, TransferMethodFactory
from payouts.models import Event, TransferMethod as amuse_trm
from countries.tests.factories import CurrencyFactory


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
        self.hw_user = User(self.payee_defaults)
        self.provide = ProviderFactory(
            name="HW_PROGRAM_WORLD",
            external_id="prg-19d7ef5e-e01e-43bc-b271-79eef1062832",
        )
        self.payee = PayeeFactory(
            user=self.user, external_id="usr-3c0840da-fbf4-464d-9bcb-a16018de66b7"
        )
        self.payload = {
            "token": "trm-56b976c5-26b2-42fa-87cf-14b3366673c6",
            "type": "BANK_ACCOUNT",
        }
        self.url = reverse("transfer_method")

        self.client.force_authenticate(self.user)
        self.client.credentials(HTTP_ACCEPT=API_V5_ACCEPT_VALUE)
        self.currency = CurrencyFactory(code="USD")
        self.currency.pk = 5
        self.currency.save()

    @patch("hyperwallet.Api.getBankAccount")
    def test_create_bank_account_trm_success(self, mocked_method):
        mocked_method.return_value = TransferMethod(self.trm_defaults)
        response = self.client.post(path=self.url, data=self.payload, format="json")
        self.assertEqual(response.status_code, 201)
        self.assertTrue(response.data['is_success'])
        # Assert TransferMethod and Event objects are created on DB
        event_db = Event.objects.get(
            object_id="trm-56b976c5-26b2-42fa-87cf-14b3366673c6"
        )
        self.assertEqual(event_db.reason, "API call")
        self.assertEqual(event_db.initiator, "SYSTEM")
        self.assertIsInstance(event_db.payload, dict)

        trm_db = amuse_trm.objects.get(payee=self.payee)
        self.assertEqual(trm_db.external_id, "trm-56b976c5-26b2-42fa-87cf-14b3366673c6")
        self.assertEqual(trm_db.type, "BANK_ACCOUNT")
        self.assertEqual(trm_db.status, "ACTIVATED")
        self.assertEqual(trm_db.active, True)

    @patch("hyperwallet.Api.getBankAccount")
    def test_create_bank_account_trm_failed(self, mocked_method):
        mocked_method.side_effect = HyperwalletAPIException(
            {
                "errors": [
                    {
                        "message": "Error message",
                        "fieldName": "",
                        "code": "ERROR_CODE",
                        "relatedResources": [
                            "trm-56b976c5-26b2-42fa-87cf-14b3366673c6"
                        ],
                    }
                ]
            }
        )
        response = self.client.post(path=self.url, data=self.payload, format="json")
        self.assertEqual(response.status_code, 404)
        self.assertFalse(response.data['is_success'])

    @responses.activate
    def test_get_trm(self):
        # Create inactive trm
        TransferMethodFactory(
            payee=self.payee,
            external_id="trm-56b976c5-26b2-42fa-87cf-14b3366673aa",
            active=False,
        )
        response = self.client.get(path=self.url)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data['is_success'])
        assert len(response.data['transfer_methods']) == 0

        # Create transfer method and repeat test
        TransferMethodFactory(
            external_id="trm-56b976c5-26b2-42fa-87cf-14b3366673c6",
            payee=self.payee,
        )
        response = self.client.get(path=self.url)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data['is_success'])
        assert len(response.data['transfer_methods']) == 1

    @responses.activate
    def test_get_404_if_no_payee(self):
        add_zendesk_mock_post_response()
        new_user = UserFactory()
        self.client.force_authenticate(new_user)
        self.client.credentials(HTTP_ACCEPT=API_V5_ACCEPT_VALUE)
        response = self.client.get(path=self.url)
        self.assertFalse(response.data['is_success'])
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.data['reason'], "HW user not found")

    @patch("hyperwallet.Api.getBankAccount")
    @responses.activate
    def test_update_trm(self, mock_fnc):
        mock_fnc.return_value = TransferMethod(self.trm_defaults)
        # Create transfer method
        TransferMethodFactory(
            external_id="trm-56b976c5-26b2-42fa-87cf-14b3366673c6",
            payee=self.payee,
        )
        response = self.client.put(path=self.url, data=self.payload)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data['is_success'])

    @responses.activate
    def test_update_trm_not_exist(self):
        response = self.client.put(path=self.url, data=self.payload)
        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.data['is_success'])
        self.assertEqual(
            response.data['reason'], "TransferMethod matching query does not exist."
        )

    @patch("hyperwallet.Api.getBankAccount")
    @responses.activate
    def test_update_trm_hw_exception(self, mock_fnc):
        mock_fnc.side_effect = HyperwalletAPIException(
            {
                "errors": [
                    {
                        "message": "Error message",
                        "fieldName": "",
                        "code": "ERROR_CODE",
                        "relatedResources": [
                            "trm-56b976c5-26b2-42fa-87cf-14b3366673c6"
                        ],
                    }
                ]
            }
        )
        # Create transfer method
        TransferMethodFactory(
            external_id="trm-56b976c5-26b2-42fa-87cf-14b3366673c6",
            payee=self.payee,
        )
        response = self.client.put(path=self.url, data=self.payload)
        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.data['is_success'])
