from unittest import mock, skip
import json
import responses
from decimal import Decimal
from unittest.mock import Mock, patch
from waffle.models import Switch, Flag
from django.test import TestCase, RequestFactory
from hyperwallet.models import (
    User,
    Payment,
)
from hyperwallet.exceptions import HyperwalletAPIException
from countries.tests.factories import CurrencyFactory, CountryFactory
from users.tests.factories import UserFactory
from payouts.tests.factories import (
    ProviderFactory,
    PayeeFactory,
    TransferMethodFactory,
    PaymentFactory,
    TransferMethodCofigurationFactory,
)
from amuse.api.v5.serializers.payout_payment import (
    CreatePaymentSerializer,
    GetPaymentSerializer,
)
from payouts.models import Payee, Event, TransferMethod, Payment as amuse_pmt
from amuse.vendor.revenue.client import (
    URL_RECORD_HYPERWALLET_WITHDRAWAL,
    URL_SUMMARY_BALANCE,
    URL_UPDATE_HYPERWALLET_WITHDRAWAL,
)


class TestPaymentSerializers(TestCase):
    @mock.patch("amuse.tasks.zendesk_create_or_update_user")
    def setUp(self, mock_zendesk):
        self.currency = CurrencyFactory(code='USD')
        self.country = CountryFactory(code="US", name="United States of America")
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
            payee=self.payee,
            external_id=self.trm_defaults['token'],
            currency=self.currency,
        )
        self.to_serializer = {
            "destination_token": "trm-56b976c5-26b2-42fa-87cf-14b3366673c6",
        }
        self.request = RequestFactory().post('/payouts/payment/')
        self.request.user = self.user
        self.context = {'request': self.request}
        self.serializer = CreatePaymentSerializer(
            request=self.request, data=self.to_serializer
        )
        self.serializer.context['request'] = self.request

        self.defaut_response = {
            "amount": "20.50",
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

        self.trm_config = TransferMethodCofigurationFactory(
            provider=self.provide, country=self.country, currency=self.currency
        )

    @mock.patch("amuse.tasks.zendesk_create_or_update_user")
    @responses.activate
    def test_payee_validator_invalid_payee(self, mock_fnc):
        new_user = UserFactory()
        request = RequestFactory().post('/payouts/payment/')
        responses.add(
            responses.GET,
            URL_SUMMARY_BALANCE % new_user.pk,
            json.dumps({"total": 20.50}),
            status=200,
        )
        request.user = new_user
        context = {'request': self.request}
        serializer = CreatePaymentSerializer(request=request, data=self.to_serializer)
        serializer.context['request'] = request
        self.assertFalse(serializer.is_valid())
        error = serializer.errors['non_field_errors'][0]
        assert error.code == "PAYEE_DOES_NOT_EXIST_DB"

    @mock.patch("amuse.tasks.zendesk_create_or_update_user")
    @responses.activate
    def test_payee_validator_invalid_payee_status(self, mock_fnc):
        self.payee.status = "LOCKED"
        self.payee.save()
        responses.add(
            responses.GET,
            URL_SUMMARY_BALANCE % self.user.pk,
            json.dumps({"total": 20.50}),
            status=200,
        )

        self.assertFalse(self.serializer.is_valid())
        error = self.serializer.errors['non_field_errors'][0]
        assert error.code == "INVALID_PAYEE_ACCOUNT_STATUS"

    @mock.patch("amuse.tasks.zendesk_create_or_update_user")
    @responses.activate
    def test_payee_validator_invalid_trm(self, mock_fnc):
        self.to_serializer['destination_token'] = 'trm-does-not-exist'
        responses.add(
            responses.GET,
            URL_SUMMARY_BALANCE % self.user.pk,
            json.dumps({"total": 20.50}),
            status=200,
        )
        self.assertFalse(self.serializer.is_valid())
        error = self.serializer.errors['non_field_errors'][0]
        assert error.code == "TRM_DOES_NOT_EXIST_DB"

    @mock.patch("amuse.tasks.zendesk_create_or_update_user")
    @responses.activate
    def test_get_balance_returnNone(self, mock_fnc):
        responses.add(
            responses.GET,
            URL_SUMMARY_BALANCE % self.user.pk,
            json.dumps({"total": None}),
            status=200,
        )
        self.assertFalse(self.serializer.is_valid())
        error = self.serializer.errors['non_field_errors'][0]
        assert error.code == "INVALID_BALANCE"

    @mock.patch('hyperwallet.Api.createPayment')
    @responses.activate
    def test_creaate_payment_success(
        self,
        mock_hw_payment_create,
    ):
        mock_hw_payment_create.return_value = Payment(self.defaut_response)
        responses.add(
            responses.GET,
            URL_SUMMARY_BALANCE % self.user.pk,
            json.dumps({"total": 90000.00}),
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
        self.assertTrue(self.serializer.is_valid())
        data = self.serializer.save()
        self.assertTrue(data['is_success'])
        self.assertEqual(data['data']['status'], "COMPLETED")
        self.assertIsInstance(data['data']['transfer_method'], dict)

        # Assert DB data is written
        pmt_db = amuse_pmt.objects.get(external_id=self.defaut_response['token'])
        self.assertEqual(pmt_db.status, 'COMPLETED')
        self.assertEqual(pmt_db.amount, Decimal('20.50'))
        self.assertEqual(pmt_db.currency.code, 'USD')
        self.assertEqual(
            pmt_db.revenue_system_id, "6e570b62-7f8d-41ee-8b99-e611d9f3626d"
        )
        self.assertEqual(pmt_db.payment_type, amuse_pmt.TYPE_ROYALTY)

        pmt_event = Event.objects.get(object_id=self.defaut_response['token'])

        self.assertEqual(pmt_event.reason, "API call")
        self.assertEqual(pmt_event.initiator, "SYSTEM")
        self.assertEqual(pmt_event.payload['status'], "COMPLETED")

    @responses.activate
    @mock.patch("amuse.tasks.zendesk_create_or_update_user")
    def test_get_payments_serializer(self, mock_fnc):
        trm = TransferMethodFactory(
            external_id="trm-56b976c5-26b2-42fa-87cf-14b33666745z"
        )
        PaymentFactory(
            external_id="pmt-56b976c5-26b2-42fa-87cf-14b3366673c6",
            payee=self.payee,
            transfer_method=trm,
        )
        qs = amuse_pmt.objects.filter(payee=self.payee)
        serializer_class = GetPaymentSerializer(qs, many=True)
        data = serializer_class.to_representation(qs)
        self.assertIsInstance(data, list)
        self.assertEqual(len(data), 1)
        self.assertIsInstance(data[0]["transfer_method"], dict)
        self.assertIsInstance(data[0]["transfer_method"]['type'], str)
        self.assertIsInstance(data[0]["transfer_method"]['status'], str)

    @mock.patch("amuse.tasks.zendesk_create_or_update_user")
    @responses.activate
    def test_get_balance_less_then_min_amount(self, mock_fnc):
        responses.add(
            responses.GET,
            URL_SUMMARY_BALANCE % self.user.pk,
            json.dumps({"total": 1.00}),
            status=200,
        )
        self.assertFalse(self.serializer.is_valid())
        error = self.serializer.errors['non_field_errors'][0]
        assert error.code == "INVALID_BALANCE_MIN_LIMIT"

    @mock.patch("amuse.tasks.zendesk_create_or_update_user")
    @responses.activate
    def test_get_balance_greater_then_max_amount(self, mock_fnc):
        responses.add(
            responses.GET,
            URL_SUMMARY_BALANCE % self.user.pk,
            json.dumps({"total": 1000000.00}),
            status=200,
        )
        self.assertFalse(self.serializer.is_valid())
        error = self.serializer.errors['non_field_errors'][0]
        assert error.code == "INVALID_BALANCE_MAX_LIMIT"

    @mock.patch("amuse.tasks.zendesk_create_or_update_user")
    @mock.patch(
        "amuse.api.v5.serializers.payout_payment.CreatePaymentSerializer._get_default_overrides"
    )
    @responses.activate
    def test_maintenance_on(self, mock_fnc_overrides, mock_fnc_user):
        mock_fnc_overrides.return_value = {
            "is_maintenance_on": True,
            "is_user_excluded": False,
            "is_max_overriden": False,
        }

        responses.add(
            responses.GET,
            URL_SUMMARY_BALANCE % self.user.pk,
            json.dumps({"total": 100.00}),
            status=200,
        )
        self.assertFalse(self.serializer.is_valid())
        error = self.serializer.errors['non_field_errors'][0]
        assert error.code == "PAYOUTS_MAINTENANCE"

    @mock.patch("amuse.tasks.zendesk_create_or_update_user")
    @mock.patch(
        "amuse.api.v5.serializers.payout_payment.CreatePaymentSerializer._get_default_overrides"
    )
    @responses.activate
    def test_user_excluded(self, mock_fnc_overrides, mock_fnc_user):
        mock_fnc_overrides.return_value = {
            "is_maintenance_on": False,
            "is_user_excluded": True,
            "is_max_overriden": False,
        }

        responses.add(
            responses.GET,
            URL_SUMMARY_BALANCE % self.user.pk,
            json.dumps({"total": 100.00}),
            status=200,
        )
        self.assertFalse(self.serializer.is_valid())
        error = self.serializer.errors['non_field_errors'][0]
        assert error.code == "PAYOUTS_USER_EXCLUDED"

    @mock.patch("amuse.tasks.zendesk_create_or_update_user")
    @mock.patch(
        "amuse.api.v5.serializers.payout_payment.CreatePaymentSerializer._get_default_overrides"
    )
    @mock.patch('hyperwallet.Api.createPayment')
    @responses.activate
    def test_user_excluded(self, mock_hw_api, mock_fnc_overrides, mock_fnc_user):
        mock_fnc_overrides.return_value = {
            "is_maintenance_on": False,
            "is_user_excluded": False,
            "is_max_overriden": True,
        }
        mock_hw_api.return_value = Payment(self.defaut_response)
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
        self.assertTrue(self.serializer.is_valid())
        data = self.serializer.save()
        self.assertTrue(data['is_success'])
        self.assertEqual(data['data']['status'], "COMPLETED")

        # Assert DB data is written
        pmt_db = amuse_pmt.objects.get(external_id=self.defaut_response['token'])
        self.assertEqual(pmt_db.status, 'COMPLETED')
        self.assertEqual(pmt_db.amount, Decimal('20.50'))
        self.assertEqual(pmt_db.currency.code, 'USD')

        pmt_event = Event.objects.get(object_id=self.defaut_response['token'])

        self.assertEqual(pmt_event.reason, "API call")
        self.assertEqual(pmt_event.initiator, "SYSTEM")
        self.assertEqual(pmt_event.payload['status'], "COMPLETED")

    @mock.patch('hyperwallet.Api.createPayment')
    @mock.patch('amuse.vendor.revenue.client.update_withdrawal')
    @responses.activate
    def test_cancel_on_error(
        self,
        mock_revenue_call,
        mock_hw_payment_create,
    ):
        mock_hw_payment_create.side_effect = HyperwalletAPIException(
            {
                "errors": [
                    {
                        "message": "PayPal transfer method email address should be same as profile email address.",
                        "code": "CONSTRAINT_VIOLATIONS",
                    }
                ]
            }
        )
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

        self.assertTrue(self.serializer.is_valid())
        data = self.serializer.save()
        self.assertFalse(data['is_success'])
        self.assertTrue(data['cancel_revenue_payment'])

    @mock.patch('hyperwallet.Api.createPayment')
    @mock.patch('amuse.vendor.revenue.client.update_withdrawal')
    @responses.activate
    def test_do_not_cancel_on_communication_error(
        self,
        mock_revenue_call,
        mock_hw_payment_create,
    ):
        mock_hw_payment_create.side_effect = HyperwalletAPIException(
            {
                "errors": [
                    {
                        "message": "Connection reset by peer.",
                        "code": "COMMUNICATION_ERROR",
                    }
                ]
            }
        )
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

        self.assertTrue(self.serializer.is_valid())
        data = self.serializer.save()
        self.assertFalse(data['is_success'])
        self.assertFalse(data['cancel_revenue_payment'])

    @mock.patch('hyperwallet.Api.createPayment')
    @responses.activate
    def test_unable_to_record_transaction_slayer(
        self,
        mock_hw_payment_create,
    ):
        mock_hw_payment_create.return_value = Payment(self.defaut_response)
        responses.add(
            responses.GET,
            URL_SUMMARY_BALANCE % self.user.pk,
            json.dumps({"total": 90000.00}),
            status=200,
        )
        response = {"transaction_id": "6e570b62-7f8d-41ee-8b99-e611d9f3626d"}

        responses.add(
            responses.POST,
            URL_RECORD_HYPERWALLET_WITHDRAWAL,
            None,
            status=200,
        )

        self.assertTrue(self.serializer.is_valid())
        data = self.serializer.save()
        self.assertFalse(data['is_success'])
        self.assertEqual(data['reason'], 'Unable to record transaction on slayer')
