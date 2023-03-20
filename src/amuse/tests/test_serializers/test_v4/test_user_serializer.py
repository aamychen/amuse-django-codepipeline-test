from unittest.mock import Mock, patch

import responses
from django.test import TestCase, override_settings, RequestFactory
from django.utils import timezone

from amuse.api.v4.serializers.user import UserSerializer
from amuse.tests.helpers import (
    ZENDESK_MOCK_API_URL_TOKEN,
    add_zendesk_mock_post_response,
)
from users.tests.factories import UserFactory, AppsflyerDeviceFactory
from users.models import AppsflyerDevice


@override_settings(**ZENDESK_MOCK_API_URL_TOKEN)
class TestUserSerializer(TestCase):
    def setUp(self):
        self.mock_user = Mock(id=1, releases=[], created=timezone.now())
        self.serializer = UserSerializer()

        self.users_request_body = {
            "first_name": "FirstNameTest",
            "last_name": "LastNameTest",
            "email": "test@example.com",
            "phone": "+38762123456",
            "country": "SE",
            "language": "sv",
            "profile_link": "",
            "profile_photo": "https://lh4.googleusercontent.com/-q_FgGnr8_DE/AAAAAAAAAAI/AAAAAAAAAAA/AIcfdXBuzCPn8xoNdpfdifG9Tq6OzcG-mw/s400/phot.jpg",
            "facebook_id": "",
            "google_id": "",
            "firebase_token": "test-123",
            "password": "password",
            "facebook_access_token": "",
            "google_id_token": "",
            "artist_name": "ArtistTest",
            "apple_signin_id": "",
            "impact_click_id": "123",
        }

    def test_free_subscription_does_not_have_is_pro_flag(self):
        self.mock_user.is_pro = False
        serialized_user = self.serializer.to_representation(instance=self.mock_user)
        assert not serialized_user['is_pro']

    def test_pro_subscription_has_is_pro_flag(self):
        self.mock_user.is_pro = True
        serialized_user = self.serializer.to_representation(instance=self.mock_user)
        assert serialized_user['is_pro']

    @responses.activate
    def test_email_must_be_unique(self):
        add_zendesk_mock_post_response()
        user = UserFactory()
        data = user.__dict__
        data.update({'facebook_access_token': '123', 'google_id_token': '123'})

        serializer = UserSerializer(data=data)

        self.assertFalse(serializer.is_valid())
        self.assertEqual(
            str(serializer.errors['email'][0]), 'user with this email already exists.'
        )

    @responses.activate
    def test_apple_signin_id_must_be_unique(self):
        add_zendesk_mock_post_response()
        apple_signin_id = '900123'
        user = UserFactory(apple_signin_id=apple_signin_id)
        data = user.__dict__
        data.update({'facebook_access_token': '123', 'google_id_token': '123'})

        serializer = UserSerializer(data=data)

        self.assertFalse(serializer.is_valid())
        self.assertEqual(
            str(serializer.errors['apple_signin_id'][0]),
            'Only one Amuse account allowed per Apple sign-in',
        )

    @patch("amuse.tasks.send_segment_signup_completed_event.delay")
    @patch("amuse.tasks.zendesk_create_or_update_user")
    def test_send_signup_completed_event_success(self, _, mock_task):
        signup_path = 'regular'

        headers = {
            'HTTP_X_TRIGGER_EVENT': '1',
            'HTTP_CF_IPCOUNTRY': 'BA',
            'HTTP_X_USER_AGENT': 'amuse-web/7adf860;',
        }
        mocked_request = RequestFactory().post(
            f'users/', self.users_request_body, **headers
        )

        user = UserFactory()
        data = user.__dict__

        self.serializer = UserSerializer(data=data, context={'request': mocked_request})

        self.serializer.send_signup_completed_event(user, signup_path)

        mock_task.assert_called_once()

    @patch("amuse.tasks.send_segment_signup_completed_event.delay")
    @patch("amuse.tasks.zendesk_create_or_update_user")
    def test_send_signup_completed_event_not_called_empty_request(self, _, mock_task):
        signup_path = 'regular'

        headers = {
            'HTTP_X_TRIGGER_EVENT': '1',
            'HTTP_CF_IPCOUNTRY': 'BA',
            'HTTP_X_USER_AGENT': 'amuse-web/7adf860;',
        }
        mocked_request = None

        user = UserFactory()
        data = user.__dict__

        self.serializer = UserSerializer(data=data, context={'request': mocked_request})

        self.serializer.send_signup_completed_event(user, signup_path)

        mock_task.assert_not_called()

    @patch("amuse.tasks.send_segment_signup_completed_event.delay")
    @patch("amuse.tasks.zendesk_create_or_update_user")
    def test_send_signup_completed_event_not_called_header_does_not_exist(
        self, _, mock_task
    ):
        signup_path = 'regular'

        headers = {'HTTP_CF_IPCOUNTRY': 'BA', 'HTTP_X_USER_AGENT': 'amuse-web/7adf860;'}
        mocked_request = RequestFactory().post(
            f'users/', self.users_request_body, **headers
        )

        user = UserFactory()
        data = user.__dict__

        self.serializer = UserSerializer(data=data, context={'request': mocked_request})

        self.serializer.send_signup_completed_event(user, signup_path)

        mock_task.assert_not_called()

    @patch("amuse.tasks.send_segment_signup_completed_event.delay")
    @patch("amuse.tasks.zendesk_create_or_update_user")
    def test_send_signup_completed_event_not_called_header_not_equal_1(
        self, _, mock_task
    ):
        signup_path = 'regular'

        headers = {
            'HTTP_X_TRIGGER_EVENT': '3',
            'HTTP_CF_IPCOUNTRY': 'BA',
            'HTTP_X_USER_AGENT': 'amuse-web/7adf860;',
        }
        mocked_request = RequestFactory().post(
            f'users/', self.users_request_body, **headers
        )

        user = UserFactory()
        data = user.__dict__

        self.serializer = UserSerializer(data=data, context={'request': mocked_request})

        self.serializer.send_signup_completed_event(user, signup_path)

        mock_task.assert_not_called()

    @patch("amuse.tasks.zendesk_create_or_update_user")
    def test_appsflyer_device_object_created_on_signup(self, _):
        appsflyer_device_info = {
            "appsflyer_id": "5",
            "idfa": "AAAAAAAA-BBBB-CCCC-DDDD-123456789876",
        }
        self.users_request_body.update(appsflyer_device_info)
        mocked_request = RequestFactory().post(f'users/', self.users_request_body)

        self.serializer = UserSerializer(
            data=self.users_request_body, context={'request': mocked_request}
        )
        self.assertTrue(self.serializer.is_valid())

        self.serializer.create(self.serializer.validated_data)

        device_exists = AppsflyerDevice.objects.filter(appsflyer_id='5').exists()
        self.assertTrue(device_exists)
        device = AppsflyerDevice.objects.filter(appsflyer_id='5').first()
        self.assertEqual(device.idfa, 'AAAAAAAA-BBBB-CCCC-DDDD-123456789876')

    @patch("amuse.tasks.zendesk_create_or_update_user")
    def test_appsflyer_device_object_not_created_no_data_in_request(self, _):
        mocked_request = RequestFactory().post(f'users/', self.users_request_body)

        self.serializer = UserSerializer(
            data=self.users_request_body, context={'request': mocked_request}
        )
        self.assertTrue(self.serializer.is_valid())

        self.serializer.create(self.serializer.validated_data)

        devices_count = AppsflyerDevice.objects.all().count()

        self.assertEqual(devices_count, 0)

    @patch("amuse.tasks.zendesk_create_or_update_user")
    def test_appsflyer_device_object_updated_device_already_exists(self, _):
        # Existing device
        device = AppsflyerDeviceFactory(appsflyer_id='5')

        self.assertIsNone(device.idfa)
        self.assertIsNone(device.idfv)
        self.assertIsNone(device.aaid)
        self.assertIsNone(device.oaid)
        self.assertIsNone(device.imei)

        appsflyer_device_info = {
            "appsflyer_id": "5",
            "idfa": "AAAAAAAA-BBBB-CCCC-DDDD-192837465743",
            "idfv": "eeeeeeee-ffff-gggg-hhhh-987654321234",
            "aaid": "iiiiiiii-jjjj-kkkk-llll-123456789101",
            "oaid": "mmmmmmmm-nnnn-oooo-pppp-192837463823",
            "imei": "AA-BBBBBB-CCCCCC-D",
        }
        self.users_request_body.update(appsflyer_device_info)
        mocked_request = RequestFactory().post(f'users/', self.users_request_body)

        self.serializer = UserSerializer(
            data=self.users_request_body, context={'request': mocked_request}
        )
        self.assertTrue(self.serializer.is_valid())

        self.serializer.create(self.serializer.validated_data)

        device_exists = AppsflyerDevice.objects.filter(appsflyer_id='5').exists()
        self.assertTrue(device_exists)
        device = AppsflyerDevice.objects.filter(appsflyer_id='5').first()
        self.assertEqual(device.idfa, 'AAAAAAAA-BBBB-CCCC-DDDD-192837465743')
        self.assertEqual(device.idfv, 'eeeeeeee-ffff-gggg-hhhh-987654321234')
        self.assertEqual(device.aaid, 'iiiiiiii-jjjj-kkkk-llll-123456789101')
        self.assertEqual(device.oaid, 'mmmmmmmm-nnnn-oooo-pppp-192837463823')
        self.assertEqual(device.imei, 'AA-BBBBBB-CCCCCC-D')
