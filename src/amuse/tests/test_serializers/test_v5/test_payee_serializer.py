from unittest import mock
from django.test import TestCase, RequestFactory
from hyperwallet.models import User
from hyperwallet.exceptions import HyperwalletAPIException
from users.tests.factories import UserFactory
from payouts.tests.factories import ProviderFactory, PayeeFactory
from amuse.api.v5.serializers.payee import (
    CreatePayeeSerializer,
    GetPayeeSerializer,
    UpdatePayeeSerializer,
)
from payouts.models import Payee, Event
from amuse.vendor.hyperwallet.client_factory import HyperWalletEmbeddedClientFactory


class TestPayeeSerializers(TestCase):
    @mock.patch("amuse.tasks.zendesk_create_or_update_user")
    def setUp(self, mock_zendesk):
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
        self.to_serializer = {
            "profile_type": "INDIVIDUAL",
            "dob": "1980-01-01",
            "address": "123 Main Street",
            "city": "New York",
            "state_province": "NY",
            "postal_code": "10016",
        }
        self.request = RequestFactory().post('/payouts/payee/')
        self.request.user = self.user
        self.context = {'request': self.request}
        self.serializer = CreatePayeeSerializer(data=self.to_serializer)
        self.serializer.context['request'] = self.request

    @mock.patch("hyperwallet.Api.createUser")
    def test_save_success(self, mock_method):
        mock_method.return_value = self.hw_user
        self.assertTrue(self.serializer.is_valid())
        data = self.serializer.save()
        hw_client = HyperWalletEmbeddedClientFactory().create(
            country_code=self.user.country
        )
        payload = self.serializer._get_create_payload(
            user=self.user, program_token=hw_client.programToken
        )
        self.assertTrue(data['is_success'])

        # Assert phone number
        self.assertEquals(payload.get('phoneNumber'), '+524423439277')

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

    @mock.patch("hyperwallet.Api.createUser")
    def test_save_failed(self, mock_method):
        mock_method.side_effect = HyperwalletAPIException(
            {
                "errors": [
                    {
                        "message": "The value you provided for this field is already registered with another user usr-3c0840da-fbf4-464d-9bcb-a16018de66b7",
                        "fieldName": "clientUserId",
                        "code": "DUPLICATE_CLIENT_USER_ID",
                        "relatedResources": [
                            "usr-3c0840da-fbf4-464d-9bcb-a16018de66b7"
                        ],
                    }
                ]
            }
        )
        self.assertTrue(self.serializer.is_valid())
        data = self.serializer.save()
        self.assertFalse(data['is_success'])
        self.assertIsNotNone(data['reason'])
        self.assertIsInstance(data['reason']['errors'], list)

    @mock.patch("amuse.tasks.zendesk_create_or_update_user")
    def test_get_payee_serializer(self, mock_method):
        payee = PayeeFactory()
        data = GetPayeeSerializer().to_representation(instance=payee)
        self.assertIsInstance(data, dict)

    @mock.patch("hyperwallet.Api.updateUser")
    @mock.patch("amuse.tasks.zendesk_create_or_update_user")
    def test_update_payee_serializer_success(self, mock_task, mock_fnc):
        payee = PayeeFactory(user=self.user, external_id=self.defaults['token'])
        mock_fnc.return_value = self.hw_user
        to_serializer = {"address2": "Zagrebacka 9"}
        serializer = UpdatePayeeSerializer(
            data=to_serializer, context={'user': self.user}
        )
        self.assertTrue(serializer.is_valid())
        hw_payload = serializer._get_update_payload(self.user)
        data = serializer.update(payee, to_serializer)
        self.assertTrue(data['is_success'])
        # Assert update Event is created
        event = Event.objects.get(
            object_id=self.defaults['token'], reason="API call UPDATE"
        )
        self.assertEqual(hw_payload['firstName'], self.user.first_name)
        self.assertEqual(hw_payload['lastName'], self.user.last_name)
        self.assertEqual(hw_payload['email'], self.user.email)
        self.assertEqual(hw_payload['phone'], self.user.phone)

    @mock.patch("hyperwallet.Api.updateUser")
    @mock.patch("amuse.tasks.zendesk_create_or_update_user")
    def test_update_payee_serializer_failed_hw_error(self, mock_task, mock_fnc):
        payee = PayeeFactory(user=self.user, external_id=self.defaults['token'])
        mock_fnc.side_effect = HyperwalletAPIException(
            {
                "errors": [
                    {
                        "message": "Error messaage",
                        "fieldName": "clientUserId",
                        "code": "ERROR_CODE",
                        "relatedResources": [
                            "usr-3c0840da-fbf4-464d-9bcb-a16018de66b7"
                        ],
                    }
                ]
            }
        )
        to_serializer = {"addressLine2": "Zagrebacka 9"}
        serializer = UpdatePayeeSerializer(
            data=to_serializer, context={'user': self.user}
        )
        self.assertTrue(serializer.is_valid())
        data = serializer.update(payee, to_serializer)
        self.assertFalse(data['is_success'])
        self.assertTrue(data['reason']['errors'] is not None)

    @mock.patch("hyperwallet.Api.updateUser")
    @mock.patch("amuse.tasks.zendesk_create_or_update_user")
    def test_update_payee_serializer_failed_event_write(self, mock_task, mock_fnc):
        payee = PayeeFactory(user=self.user, external_id=self.defaults['token'])
        mock_fnc.return_value = None
        to_serializer = {"address2": "Zagrebacka 9"}
        serializer = UpdatePayeeSerializer(
            data=to_serializer, context={'user': self.user}
        )
        self.assertTrue(serializer.is_valid())
        data = serializer.update(payee, to_serializer)
        self.assertFalse(data['is_success'])
        self.assertTrue(data['reason'] is not None)

    @mock.patch("hyperwallet.Api.createUser")
    def test_phone_is_required(self, mock_method):
        self.user.phone = None
        self.user.phone_verified = False
        self.user.save()
        mock_method.return_value = self.hw_user
        self.assertFalse(self.serializer.is_valid())
        error_dict = self.serializer.errors
        self.assertIsInstance(error_dict, dict)
        error_list = error_dict.get("non_field_errors")
        error_obj = error_list[0]
        self.assertEqual(error_obj.code, "UNVALIDATED_PHONE")

    @mock.patch("hyperwallet.Api.createUser")
    def test_government_id_is_required_for_SE(self, mock_method):
        self.user.country = "SE"
        self.user.save()
        mock_method.return_value = self.hw_user
        self.assertFalse(self.serializer.is_valid())
        error_dict = self.serializer.errors
        self.assertIsInstance(error_dict, dict)
        error_obj = error_dict.get("government_id")
        self.assertEqual(error_obj[0], "government_id is not valid")

    @mock.patch("hyperwallet.Api.updateUser")
    @mock.patch("amuse.tasks.zendesk_create_or_update_user")
    def test_update_property_is_null(self, mock_task, mock_fnc):
        payee = PayeeFactory(user=self.user, external_id=self.defaults['token'])
        mock_fnc.return_value = self.hw_user
        to_serializer = {"address": "Zagrebacka 9", "middle_name": None, "address2": ""}
        serializer = UpdatePayeeSerializer(
            data=to_serializer, context={'user': self.user}
        )
        self.assertEqual(serializer.is_valid(), True)
        hw_payload = serializer._get_update_payload(self.user)
        self.assertEqual(hw_payload['middleName'], None)
        self.assertEqual(hw_payload['addressLine2'], None)
        data = serializer.update(payee, to_serializer)
        self.assertTrue(data['is_success'])
        # Assert update Event is created
        event = Event.objects.get(
            object_id=self.defaults['token'], reason="API call UPDATE"
        )
        self.assertEqual(hw_payload['firstName'], self.user.first_name)
        self.assertEqual(hw_payload['lastName'], self.user.last_name)
        self.assertEqual(hw_payload['email'], self.user.email)
        self.assertEqual(hw_payload['phone'], self.user.phone)

    @mock.patch("hyperwallet.Api.createUser")
    def test_city_len_validatio(self, mock_method):
        mock_method.return_value = self.hw_user
        to_serializer = {
            "profile_type": "INDIVIDUAL",
            "dob": "1980-01-01",
            "address": "123 Main Street",
            "city": "VeryLong City Name VeryLong City Name VeryLong City",
            "state_province": "NY",
            "postal_code": "10016",
        }
        serializer = CreatePayeeSerializer(data=to_serializer)
        self.assertFalse(serializer.is_valid())
        error_dict = serializer.errors
        err_obj = error_dict['city'][0]
        self.assertEqual(err_obj.code, 'max_length')
