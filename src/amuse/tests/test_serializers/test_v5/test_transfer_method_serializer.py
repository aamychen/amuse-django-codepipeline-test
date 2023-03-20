from unittest import mock
from unittest.mock import Mock, patch
from django.test import TestCase, RequestFactory
from hyperwallet.models import (
    User,
    BankAccount,
    PayPalAccount,
    BankCard,
    PrepaidCard,
    PaperCheck,
    VenmoAccount,
)
from hyperwallet.exceptions import HyperwalletAPIException
from users.tests.factories import UserFactory
from payouts.tests.factories import ProviderFactory, PayeeFactory, TransferMethodFactory
from amuse.api.v5.serializers.transfer_method import (
    CreateTransferMethodSerializer,
    GetTransferMethodSerializer,
)
from payouts.models import Payee, Event, TransferMethod
from countries.tests.factories import CurrencyFactory


class TestCreateTransferMethodSerializers(TestCase):
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
        self.to_serializer = {
            "token": "trm-56b976c5-26b2-42fa-87cf-14b3366673c6",
            "type": "BANK_ACCOUNT",
        }
        self.request = RequestFactory().post('/payouts/transfer-method//')
        self.request.user = self.user
        self.context = {'request': self.request}
        self.serializer = CreateTransferMethodSerializer(data=self.to_serializer)
        self.serializer.context['request'] = self.request
        self.currency = CurrencyFactory(code="USD")
        self.currency.pk = 5
        self.currency.save()

    def _build_trm_object(self, type):
        trm_defaults = {
            "token": "trm-56b976c5-26b2-42fa-87cf-14b3366673c6",
            "type": type,
            "status": "ACTIVATED",
            "transferMethodCurrency": "USD",
        }
        if type == 'BANK_ACCOUNT':
            return BankAccount(trm_defaults)
        elif type == 'WIRE_ACCOUNT':
            return BankAccount(trm_defaults)
        elif type == "PAYPAL_ACCOUNT":
            return PayPalAccount(trm_defaults)
        elif type == 'BANK_CARD':
            return BankCard(trm_defaults)
        elif type == 'VENMO_ACCOUNT':
            return VenmoAccount(trm_defaults)
        elif type == 'PREPAID_CARD':
            return PrepaidCard(trm_defaults)
        elif type == 'PAPER_CHECK':
            return PaperCheck(trm_defaults)

    def _assert_db_data_created(self, type):
        trm_db = TransferMethod.objects.get(
            external_id='trm-56b976c5-26b2-42fa-87cf-14b3366673c6'
        )
        event = Event.objects.get(object_id='trm-56b976c5-26b2-42fa-87cf-14b3366673c6')
        self.assertEqual(trm_db.status, "ACTIVATED")
        self.assertEqual(trm_db.type, type)
        self.assertEqual(trm_db.active, True)
        self.assertEqual(trm_db.provider, self.provide)
        self.assertEqual(trm_db.payee, self.payee)
        self.assertEqual(trm_db.currency.code, "USD")

        self.assertEqual(
            event.payload['token'], 'trm-56b976c5-26b2-42fa-87cf-14b3366673c6'
        )
        self.assertEqual(event.reason, "API call")
        self.assertEqual(event.initiator, "SYSTEM")

    def test_unsupported_trm(self):
        fake_data = {
            "token": "trm-56b976c5-26b2-42fa-87cf-14b3366673c6",
            "type": "FAKE_ACCOUNT",
        }
        serializer = CreateTransferMethodSerializer(data=fake_data)
        serializer.context['request'] = self.request
        serializer.is_valid()
        data = serializer.save()
        self.assertEqual(data['is_success'], False)
        self.assertEqual(data['reason'], "Unsupported transfer method")

    @patch("hyperwallet.Api.getBankAccount")
    def test_bank_account_trm(self, mock_func):
        mock_func.return_value = self._build_trm_object("BANK_ACCOUNT")
        self.serializer.is_valid()
        data = self.serializer.save()
        self.assertTrue(data['is_success'])
        self.assertEqual(data['data']['status'], "ACTIVATED")
        self.assertEqual(data['data']['type'], "BANK_ACCOUNT")
        self.assertEqual(
            data['data']['token'], "trm-56b976c5-26b2-42fa-87cf-14b3366673c6"
        )
        self._assert_db_data_created("BANK_ACCOUNT")

    @patch("hyperwallet.Api.getBankAccount")
    def test_bank_account_trm_wire_account(self, mock_func):
        mock_func.return_value = self._build_trm_object("WIRE_ACCOUNT")
        self.serializer.is_valid()
        data = self.serializer.save()
        self.assertTrue(data['is_success'])
        self.assertEqual(data['data']['status'], "ACTIVATED")
        self.assertEqual(data['data']['type'], "WIRE_ACCOUNT")
        self.assertEqual(
            data['data']['token'], "trm-56b976c5-26b2-42fa-87cf-14b3366673c6"
        )
        self._assert_db_data_created("WIRE_ACCOUNT")

    @patch("hyperwallet.Api.getPayPalAccount")
    def test_paypal_account_trm(self, mock_func):
        mock_func.return_value = self._build_trm_object("PAYPAL_ACCOUNT")
        paypal_payload = {
            "token": "trm-56b976c5-26b2-42fa-87cf-14b3366673c6",
            "type": "PAYPAL_ACCOUNT",
        }
        serializer = CreateTransferMethodSerializer(data=paypal_payload)
        serializer.context['request'] = self.request
        serializer.is_valid()
        data = serializer.save()

        self.assertTrue(data['is_success'])
        self.assertEqual(data['data']['status'], "ACTIVATED")
        self.assertEqual(data['data']['type'], "PAYPAL_ACCOUNT")
        self.assertEqual(
            data['data']['token'], "trm-56b976c5-26b2-42fa-87cf-14b3366673c6"
        )
        self._assert_db_data_created("PAYPAL_ACCOUNT")

    @patch("hyperwallet.Api.getBankCard")
    def test_bankcard_account_trm(self, mock_func):
        mock_func.return_value = self._build_trm_object("BANK_CARD")
        payload = {
            "token": "trm-56b976c5-26b2-42fa-87cf-14b3366673c6",
            "type": "BANK_CARD",
        }
        serializer = CreateTransferMethodSerializer(data=payload)
        serializer.context['request'] = self.request
        serializer.is_valid()
        data = serializer.save()

        self.assertTrue(data['is_success'])
        self.assertEqual(data['data']['status'], "ACTIVATED")
        self.assertEqual(data['data']['type'], "BANK_CARD")
        self.assertEqual(
            data['data']['token'], "trm-56b976c5-26b2-42fa-87cf-14b3366673c6"
        )
        self._assert_db_data_created("BANK_CARD")

    @patch("hyperwallet.Api.getVenmoAccount")
    def test_venmoo_account_trm(self, mock_func):
        mock_func.return_value = self._build_trm_object("VENMO_ACCOUNT")
        payload = {
            "token": "trm-56b976c5-26b2-42fa-87cf-14b3366673c6",
            "type": "VENMO_ACCOUNT",
        }
        serializer = CreateTransferMethodSerializer(data=payload)
        serializer.context['request'] = self.request
        serializer.is_valid()
        data = serializer.save()

        self.assertTrue(data['is_success'])
        self.assertEqual(data['data']['status'], "ACTIVATED")
        self.assertEqual(data['data']['type'], "VENMO_ACCOUNT")
        self.assertEqual(
            data['data']['token'], "trm-56b976c5-26b2-42fa-87cf-14b3366673c6"
        )
        self._assert_db_data_created("VENMO_ACCOUNT")

    @patch("hyperwallet.Api.getPrepaidCard")
    def test_prepaid_card_account_trm(self, mock_func):
        mock_func.return_value = self._build_trm_object("PREPAID_CARD")
        payload = {
            "token": "trm-56b976c5-26b2-42fa-87cf-14b3366673c6",
            "type": "PREPAID_CARD",
        }
        serializer = CreateTransferMethodSerializer(data=payload)
        serializer.context['request'] = self.request
        serializer.is_valid()
        data = serializer.save()

        self.assertTrue(data['is_success'])
        self.assertEqual(data['data']['status'], "ACTIVATED")
        self.assertEqual(data['data']['type'], "PREPAID_CARD")
        self.assertEqual(
            data['data']['token'], "trm-56b976c5-26b2-42fa-87cf-14b3366673c6"
        )
        self._assert_db_data_created("PREPAID_CARD")

    @patch("hyperwallet.Api.getPaperCheck")
    def test_paper_cheeck_account_trm(self, mock_func):
        mock_func.return_value = self._build_trm_object("PAPER_CHECK")
        payload = {
            "token": "trm-56b976c5-26b2-42fa-87cf-14b3366673c6",
            "type": "PAPER_CHECK",
        }
        serializer = CreateTransferMethodSerializer(data=payload)
        serializer.context['request'] = self.request
        serializer.is_valid()
        data = serializer.save()

        self.assertTrue(data['is_success'])
        self.assertEqual(data['data']['status'], "ACTIVATED")
        self.assertEqual(data['data']['type'], "PAPER_CHECK")
        self.assertEqual(
            data['data']['token'], "trm-56b976c5-26b2-42fa-87cf-14b3366673c6"
        )
        self._assert_db_data_created("PAPER_CHECK")

    @patch("hyperwallet.Api.getBankAccount")
    def test_hw_api_error_case(self, mock_func):
        mock_func.side_effect = HyperwalletAPIException(
            {
                'errors': [
                    {
                        'message': 'The requested resource was not found.',
                        'code': 'RESOURCE_NOT_FOUND',
                    }
                ]
            }
        )
        self.serializer.is_valid()
        data = self.serializer.save()
        self.assertFalse(data['is_success'])
        self.assertEqual(data['reason']['errors'][0]['code'], 'RESOURCE_NOT_FOUND')

    @patch("hyperwallet.Api.getBankAccount")
    def test_db_write_error_case(self, mock_func):
        mock_func.return_value = "WRONG_RETURN_VALUE"
        self.serializer.is_valid()
        data = self.serializer.save()
        self.assertFalse(data['is_success'])
        self.assertIsInstance(data['reason'], str)

    @mock.patch("amuse.tasks.zendesk_create_or_update_user")
    def test_no_payee_created(self, mock_fnc):
        request = RequestFactory().post('/transfer-method//')
        request.user = UserFactory()
        self.context = {'request': request}
        serializer = CreateTransferMethodSerializer(data=self.to_serializer)
        serializer.context['request'] = request
        serializer.is_valid()
        data = serializer.save()
        self.assertFalse(data['is_success'])
        self.assertEqual(data['reason'], "HW user does not exit in DB")

    @mock.patch("amuse.tasks.zendesk_create_or_update_user")
    def test_trm_exist_validator(self, mock_fnc):
        TransferMethodFactory(external_id="trm-56b976c5-26b2-42fa-87cf-14b3366673c6")
        self.assertFalse(self.serializer.is_valid())
        error_dict = self.serializer.errors
        self.assertIsInstance(error_dict, dict)
        error_list = error_dict.get("non_field_errors")
        error_obj = error_list[0]
        self.assertEqual(
            str(error_obj), "trm-56b976c5-26b2-42fa-87cf-14b3366673c6 already exist"
        )
        self.assertEqual(error_obj.code, "TRM_EXIST_IN_DB")

    @mock.patch("amuse.tasks.zendesk_create_or_update_user")
    def test_get_transfer_methods(self, mock_fnc):
        TransferMethodFactory(
            external_id="trm-56b976c5-26b2-42fa-87cf-14b3366673c6", payee=self.payee
        )
        qs = TransferMethod.objects.filter(payee__pk=self.user.pk)
        serializer_class = GetTransferMethodSerializer(qs, many=True)
        data = serializer_class.to_representation(qs)
        self.assertIsInstance(data, list)
        self.assertEqual(len(data), 1)
        self.assertIsInstance(data[0]['limits_and_fee'], dict)

    @patch("hyperwallet.Api.getBankAccount")
    def test_trm_lifecycle(self, mock_func):
        existig_trm = TransferMethodFactory(
            external_id="trm-56b976c5-26b2-42fa-87cf-14b3366673c5",
            payee=self.payee,
            provider=self.provide,
            currency=self.currency,
        )
        existig_trm_disabled = TransferMethodFactory(
            external_id="trm-56b976c5-26b2-42fa-87cf-14b3366673c6",
            payee=self.payee,
            active=False,
            provider=self.provide,
            currency=self.currency,
        )

        mock_func.return_value = self._build_trm_object("BANK_ACCOUNT")
        self.serializer.is_valid()
        data = self.serializer.save()
        self.assertTrue(data['is_success'])
        self.assertEqual(data['data']['status'], "ACTIVATED")
        self.assertEqual(data['data']['type'], "BANK_ACCOUNT")
        self.assertEqual(
            data['data']['token'], "trm-56b976c5-26b2-42fa-87cf-14b3366673c6"
        )
        self._assert_db_data_created("BANK_ACCOUNT")
        # Assert existing trm is now deactivated
        existig_trm.refresh_from_db()
        self.assertFalse(existig_trm.active)
        # Assert exist trm activated
        existig_trm_disabled.refresh_from_db()
        self.assertTrue(existig_trm_disabled.active)

    @patch("hyperwallet.Api.getBankAccount")
    def test_bank_account_trm_falback_to_USD(self, mock_func):
        mock_func.return_value = BankAccount(
            {
                "token": "trm-56b976c5-26b2-42fa-87cf-14b3366673c6",
                "type": "BANK_ACCOUNT",
                "status": "ACTIVATED",
                "transferMethodCurrency": "AAA",
            }
        )
        self.serializer.is_valid()
        data = self.serializer.save()
        self.assertTrue(data['is_success'])
        self.assertEqual(data['data']['status'], "ACTIVATED")
        self.assertEqual(data['data']['type'], "BANK_ACCOUNT")
        self.assertEqual(
            data['data']['token'], "trm-56b976c5-26b2-42fa-87cf-14b3366673c6"
        )
        trm_db = TransferMethod.objects.get(
            external_id="trm-56b976c5-26b2-42fa-87cf-14b3366673c6"
        )
        self.assertEqual(trm_db.currency.code, "USD")
