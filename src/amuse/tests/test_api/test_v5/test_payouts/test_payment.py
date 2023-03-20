from unittest import mock
from django.urls import reverse
import json
import responses
from decimal import Decimal
from amuse.tests.test_api.base import AmuseAPITestCase, API_V5_ACCEPT_VALUE
from hyperwallet.models import (
    User,
    Payment,
)
from countries.tests.factories import CurrencyFactory
from users.tests.factories import UserFactory
from payouts.tests.factories import (
    ProviderFactory,
    PayeeFactory,
    TransferMethodFactory,
    PaymentFactory,
)

from payouts.models import Payment as amuse_pmt
from amuse.vendor.revenue.client import (
    URL_RECORD_HYPERWALLET_WITHDRAWAL,
    URL_SUMMARY_BALANCE,
    URL_UPDATE_HYPERWALLET_WITHDRAWAL,
)


class TestPaymentViews(AmuseAPITestCase):
    @mock.patch("amuse.tasks.zendesk_create_or_update_user")
    def setUp(self, mock_zendesk):
        self.user = UserFactory(country="US", email='test@example.com')
        self.user_defaults = {
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
        self.hw_user = User(self.user_defaults)
        self.provide = ProviderFactory(
            name="HW_PROGRAM_WORLD",
            external_id="prg-19d7ef5e-e01e-43bc-b271-79eef1062832",
        )
        self.payee = PayeeFactory(
            user=self.user,
            external_id=self.user_defaults['token'],
            provider=self.provide,
        )
        self.trm_defaults = {
            "token": "trm-56b976c5-26b2-42fa-87cf-14b3366673c6",
            "type": "BANK_ACCOUNT",
        }
        self.trm = TransferMethodFactory(
            payee=self.payee, external_id=self.trm_defaults['token']
        )
        self.payment = PaymentFactory(payee=self.payee, transfer_method=self.trm)

        self.defaut_response = {
            "amount": "50.50",
            "clientPaymentId": str(self.payee.pk),
            "createdOn": "2021-07-07T17:57:17",
            "currency": "USD",
            "destinationToken": "trm-56b976c5-26b2-42fa-87cf-14b3366673c6",
            "expiresOn": "2022-01-03T17:57:17",
            "programToken": "prg-4539a19b-c3e1-44a2-9121-23c73c345c46",
            "purpose": "OTHER",
            "status": "COMPLETED",
            "token": "pmt-ebde365d-650f-408f-ac92-3a96b8e66f45",
        }

        self.currency = CurrencyFactory(code='USD')
        self.client.force_authenticate(self.user)
        self.client.credentials(HTTP_ACCEPT=API_V5_ACCEPT_VALUE)

    def test_get_payments_viewe(self):
        url = reverse("payouts_payment")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['is_success'], True)
        self.assertIsInstance(response.data['payments'], list)
        self.assertEqual(len(response.data['payments']), 1)

    @responses.activate
    @mock.patch('hyperwallet.Api.createPayment')
    def test_post_pyments_view(self, mock_fnc):
        mock_fnc.return_value = Payment(self.defaut_response)
        responses.add(
            responses.GET,
            URL_SUMMARY_BALANCE % self.user.pk,
            json.dumps({"total": 50.50}),
            status=200,
        )
        response = {"transaction_id": "6e570b62-7f8d-41ee-8b99-e611d9f3626d"}

        responses.add(
            responses.POST,
            URL_RECORD_HYPERWALLET_WITHDRAWAL,
            json.dumps(response),
            status=200,
        )

        responses.add(
            responses.PUT,
            URL_UPDATE_HYPERWALLET_WITHDRAWAL,
            json.dumps(response),
            status=200,
        )
        payload = {"destination_token": "trm-56b976c5-26b2-42fa-87cf-14b3366673c6"}
        url = reverse("payouts_payment")
        response = self.client.post(path=url, data=payload)
        self.assertEqual(response.data['is_success'], True)
        # Assert data is written to DB
        pmt = amuse_pmt.objects.get(
            external_id='pmt-ebde365d-650f-408f-ac92-3a96b8e66f45'
        )
        assert pmt.amount == Decimal(50.50)
        assert pmt.status == 'COMPLETED'
        assert pmt.transfer_method == self.trm
        assert pmt.payee == self.payee

    @responses.activate
    @mock.patch('hyperwallet.Api.createPayment')
    def test_post_pyments_view_400_balance_validaation(self, mock_fnc):
        mock_fnc.return_value = Payment(self.defaut_response)
        responses.add(
            responses.GET,
            URL_SUMMARY_BALANCE % self.user.pk,
            json.dumps({"total": 0.50}),
            status=200,
        )
        response = {"transaction_id": "6e570b62-7f8d-41ee-8b99-e611d9f3626d"}

        responses.add(
            responses.POST,
            URL_RECORD_HYPERWALLET_WITHDRAWAL,
            json.dumps(response),
            status=200,
        )

        responses.add(
            responses.PUT,
            URL_UPDATE_HYPERWALLET_WITHDRAWAL,
            json.dumps(response),
            status=200,
        )
        payload = {"destination_token": "trm-56b976c5-26b2-42fa-87cf-14b3366673c6"}
        url = reverse("payouts_payment")
        response = self.client.post(path=url, data=payload)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.data['non_field_errors'][0].code, "INVALID_BALANCE_MIN_LIMIT"
        )

    @mock.patch("amuse.tasks.zendesk_create_or_update_user")
    def test_get_payments_payee_not_exist(self, mock_zendesk):
        random_user = UserFactory()
        self.client.force_authenticate(random_user)
        url = reverse("payouts_payment")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)
        self.assertFalse(response.data["is_success"], False)
