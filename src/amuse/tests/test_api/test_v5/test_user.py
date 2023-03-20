from unittest import mock
from datetime import datetime
import responses
from django.test import override_settings
from django.urls import reverse
from rest_framework import status
from rest_framework.exceptions import ValidationError
from waffle.models import Flag, Switch
from waffle.testutils import override_switch

from amuse.api.base.viewsets.user import UserViewSet
from amuse.api.v5.serializers.user import SmsUserRateThrottle
from amuse.tests.test_api.base import (
    API_V4_ACCEPT_VALUE,
    API_V5_ACCEPT_VALUE,
    AmuseAPITestCase,
)
from amuse.throttling import SendSmsThrottle
from releases.models import RoyaltySplit, Release
from releases.tests.factories import RoyaltySplitFactory, ReleaseFactory
from users.models.user import OtpDevice, User, UserMetadata
from users.tests.factories import UserFactory, UserMetadataFactory
from django.core.cache import cache


class UserAPIV5TestCase(AmuseAPITestCase):
    @mock.patch('amuse.tasks.zendesk_create_or_update_user')
    def setUp(self, mocked_zendesk):
        self.user = UserFactory(
            phone_verified=True, otp_enabled=True, apple_signin_id='fake-apple-123'
        )
        self.client.credentials(HTTP_ACCEPT=API_V5_ACCEPT_VALUE)
        self.agent_web = 'amuse-web/9000; WiFi'
        self.agent_android = 'amuse-android/9000; IP over carrier pigeons'
        Flag.objects.create(name='2FA-web', everyone=True)
        Flag.objects.create(name='2FA-android', everyone=False)
        Switch.objects.create(
            name="verify-phone-block-mismatch-countries:enabled", active=True
        )
        cache.clear()

    @mock.patch('amuse.api.base.viewsets.user.LoginEndpointThrottle')
    @mock.patch('amuse.api.base.viewsets.user.send_sms_code')
    def test_email_invalid_username(self, mocked_sms_send, mock_throttler):
        mock_throttler.return_value = mock.Mock(allow_request=lambda a, b: True)
        url = reverse('user-email')

        # No code passed sets code, sends sms and returns 400
        data = {'email': self.user.email[:-2], 'password': UserFactory.password[:-2]}
        response = self.client.post(url, data, HTTP_USER_AGENT=self.agent_web)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.json()['email'], 'Invalid username or password')

    @mock.patch('amuse.api.base.viewsets.user.LoginSendSmsThrottle')
    @mock.patch('amuse.api.base.viewsets.user.LoginEndpointThrottle')
    @mock.patch('amuse.api.base.viewsets.user.send_sms_code')
    def test_email_login_2fa(
        self, mocked_sms_send, mocked_login_throttler, mocked_sms_throttler
    ):
        mocked_login_throttler.return_value = mock.Mock(allow_request=lambda a, b: True)
        mocked_sms_throttler.return_value = mock.Mock(allow_request=lambda a, b: True)
        url = reverse('user-email')

        # No code passed sets code, sends sms and returns 400
        data = {'email': self.user.email, 'password': UserFactory.password}
        response = self.client.post(url, data, HTTP_USER_AGENT=self.agent_web)
        otp = self.user.otpdevice
        sms_code = otp._current_code()
        message = f'Your Amuse 2FA code is {sms_code[:3]} {sms_code[3:]}'

        assert otp.otp_secret
        self.assertEqual(otp.otp_counter, 0)
        mocked_sms_send.assert_called_once_with(self.user.phone, message)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.json()['phone'], self.user.masked_phone())

        # Invalid code sent does not trigger re-send of SMS
        mocked_sms_send.reset_mock()
        data['sms_code'] = sms_code[:1]
        response = self.client.post(url, data, HTTP_USER_AGENT=self.agent_web)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        mocked_sms_send.assert_not_called()
        self.assertEqual(response.json()['sms_code'], 'Invalid code')

        # Code passed allows login
        data['sms_code'] = sms_code
        response = self.client.post(url, data, HTTP_USER_AGENT=self.agent_web)
        otp.refresh_from_db()

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(otp.otp_counter, 1)

    @mock.patch('amuse.api.base.viewsets.user.LoginEndpointThrottle')
    @mock.patch('amuse.api.base.viewsets.user.send_sms_code')
    def test_email_login_2fa_disabled_platform(self, mocked_sms_send, mock_throttler):
        mock_throttler.return_value = mock.Mock(allow_request=lambda a, b: True)
        url = reverse('user-email')
        data = {'email': self.user.email, 'password': UserFactory.password}

        response = self.client.post(url, data, HTTP_USER_AGENT=self.agent_android)

        self.assertEqual(OtpDevice.objects.count(), 0)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        mocked_sms_send.assert_not_called()

    @mock.patch('amuse.api.base.viewsets.user.LoginEndpointThrottle')
    @mock.patch('amuse.api.base.viewsets.user.send_sms_code')
    def test_email_login_2fa_old_api_version(self, mocked_sms_send, mock_throttler):
        self.client.credentials(HTTP_ACCEPT=API_V4_ACCEPT_VALUE)
        mock_throttler.return_value = mock.Mock(allow_request=lambda a, b: True)
        url = reverse('user-email')
        data = {'email': self.user.email, 'password': UserFactory.password}

        response = self.client.post(url, data, HTTP_USER_AGENT=self.agent_web)

        self.assertEqual(OtpDevice.objects.count(), 0)
        mocked_sms_send.assert_not_called()
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json(), [])

    @override_settings(ANDROID_APP_MFA_HASH='xyz-hash')
    @mock.patch('amuse.api.v5.serializers.user.send_sms_code')
    @mock.patch(
        'amuse.api.v5.serializers.user.validate_phone', return_value='+46700000000'
    )
    def test_changing_phone_number_2fa(self, mocked_validate, mocked_sms_send):
        self.user.otp_enabled = False
        self.user.save()
        UserViewSet.get_throttles = lambda x: []  # Disable SMS throttling
        SmsUserRateThrottle.rate = "10/h"
        self.client.force_authenticate(self.user)
        url = reverse('user-detail', args=[self.user.pk])
        original_phone = self.user.phone
        phone = '+46700000000'
        assert phone != original_phone
        data = {
            'country': self.user.country,
            'first_name': self.user.first_name,
            'last_name': self.user.last_name,
            'phone': phone,
            'profile_photo': 'avatar.jpg',
        }

        # Updating user creates OtpDevice and sends SMS
        response = self.client.patch(url, data, HTTP_USER_AGENT=self.agent_android)
        otp = self.user.otpdevice
        code = otp._current_code()

        assert code
        assert otp.otp_secret
        self.assertEqual(otp.otp_counter, 0)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(self.user.phone, original_phone)
        message = f'Your Amuse 2FA code is {OtpDevice.objects.first()._current_code()}\n\nxyz-hash'
        mocked_sms_send.assert_called_once_with(phone, message)

        # Update with changed phone and correct sms_code works
        data['sms_code'] = code
        response = self.client.patch(url, data)
        otp.refresh_from_db()
        self.user.refresh_from_db()

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(self.user.phone, phone)
        self.assertTrue(self.user.phone_verified)
        self.assertTrue(self.user.otp_enabled)
        self.assertEqual(otp.otp_counter, 1)

    @mock.patch('amuse.api.v5.serializers.user.send_sms_code')
    @mock.patch(
        'amuse.api.v5.serializers.user.validate_phone', return_value='+46700000000'
    )
    def test_do_not_update_apple_signin_id_if_not_provided(
        self, mocked_validate, mocked_sms_send
    ):
        UserViewSet.get_throttles = lambda x: []  # Disable SMS throttling
        SmsUserRateThrottle.rate = "10/h"
        self.client.force_authenticate(self.user)
        url = reverse('user-detail', args=[self.user.pk])
        original_apple_signin_id = self.user.apple_signin_id
        data = {
            'country': self.user.country,
            'first_name': self.user.first_name,
            'last_name': self.user.last_name,
            'phone': self.user.phone,
            'profile_photo': 'avatar.jpg',
        }

        def test(expected_apple_signin_id, body):
            response = self.client.patch(url, body)
            self.user.refresh_from_db()
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            self.assertEqual(expected_apple_signin_id, self.user.apple_signin_id)

        test(original_apple_signin_id, data)
        data.update({'apple_signin_id': 'new-fake-id'})
        test(original_apple_signin_id, data)

    @mock.patch('amuse.api.v5.serializers.user.send_sms_code')
    @mock.patch(
        'amuse.api.v5.serializers.user.validate_phone', return_value='+46700000000'
    )
    def test_change_phone_number_sms_throttle(self, mocked_validate, mocked_sms_send):
        self.user.otp_enabled = False
        self.user.save()
        UserViewSet.get_throttles = lambda x: []  # Disable SMS throttling
        SmsUserRateThrottle.rate = "1/h"
        self.client.force_authenticate(self.user)
        url = reverse('user-detail', args=[self.user.pk])
        original_phone = self.user.phone
        phone = '+46700000000'
        assert phone != original_phone
        data = {
            'country': self.user.country,
            'first_name': self.user.first_name,
            'last_name': self.user.last_name,
            'phone': phone,
            'profile_photo': 'avatar.jpg',
        }

        # Updating user creates OtpDevice and sends SMS
        response = self.client.patch(url, data)
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        mocked_sms_send.assert_called_once()

        mocked_sms_send.reset_mock()

        response = self.client.patch(url, data)
        assert response.status_code == status.HTTP_429_TOO_MANY_REQUESTS
        mocked_sms_send.assert_not_called()

    @override_switch("sinch:active:ww", active=True)
    @mock.patch('amuse.api.v5.serializers.user.send_otp_sms')
    @mock.patch(
        'amuse.api.v5.serializers.user.validate_phone', return_value='+46700000000'
    )
    def test_changing_phone_number_2fa_uses_sinch_if_applicable(
        self, mocked_validate, mocked_sms_send
    ):
        self.user.otp_enabled = False
        self.user.save()
        UserViewSet.get_throttles = lambda x: []  # Disable SMS throttling
        SmsUserRateThrottle.rate = "10/h"
        self.client.force_authenticate(self.user)
        url = reverse('user-detail', args=[self.user.pk])
        original_phone = self.user.phone
        phone = '+46700000000'
        assert phone != original_phone
        data = {
            'country': self.user.country,
            'first_name': self.user.first_name,
            'last_name': self.user.last_name,
            'phone': phone,
            'profile_photo': 'avatar.jpg',
        }

        # Updating user creates OtpDevice and sends SMS
        response = self.client.patch(url, data)
        otp = self.user.otpdevice
        code = otp._current_code()

        assert code
        assert otp.otp_secret
        self.assertEqual(otp.otp_counter, 0)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(self.user.phone, original_phone)
        mocked_sms_send.assert_called_once_with(
            phone, f'Your Amuse 2FA code is {code[:3]} {code[3:]}'
        )

        # Update with changed phone and correct sms_code works
        data['sms_code'] = code
        response = self.client.patch(url, data)
        otp.refresh_from_db()
        self.user.refresh_from_db()

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(self.user.phone, phone)
        self.assertTrue(self.user.phone_verified)
        self.assertTrue(self.user.otp_enabled)
        self.assertEqual(otp.otp_counter, 1)

    @mock.patch(
        'amuse.api.v5.serializers.user.validate_phone',
        side_effect=ValidationError({'phone': 'Invalid phone number'}),
    )
    def test_changing_phone_number_invalid_number_returns_400(self, mocked_validate):
        UserViewSet.get_throttles = lambda x: []  # Disable SMS throttling
        self.client.force_authenticate(self.user)
        url = reverse('user-detail', args=[self.user.pk])
        original_phone = self.user.phone
        phone = '+461234567890'
        data = {
            'country': self.user.country,
            'first_name': self.user.first_name,
            'last_name': self.user.last_name,
            'phone': phone,
            'profile_photo': 'avatar.jpg',
        }

        response = self.client.patch(url, data)
        self.user.refresh_from_db()

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(self.user.phone, original_phone)

    @override_settings(ANDROID_APP_MFA_HASH='xyz-hash')
    @mock.patch('amuse.api.v5.serializers.user.send_otp_sms')
    @mock.patch(
        'amuse.api.v5.serializers.user.validate_phone', return_value='+46700000000'
    )
    def test_prevent_changing_phone_number_if_2fa_not_set_up(
        self, mocked_validate, mocked_send_sms
    ):
        self.user.otp_enabled = False
        self.user.phone_verified = False
        self.user.save()

        UserViewSet.get_throttles = lambda x: []  # Disable SMS throttling
        SmsUserRateThrottle.rate = "1/h"
        self.client.force_authenticate(self.user)
        url = reverse('user-detail', args=[self.user.pk])
        original_phone = self.user.phone
        new_phone = '+46700000000'
        new_first_name = self.user.first_name + ' new name'

        assert new_phone != original_phone
        data = {
            'country': self.user.country,
            'first_name': new_first_name,
            'last_name': self.user.last_name,
            'phone': new_phone,
            'profile_photo': 'avatar.jpg',
        }

        # Updating user does not send verification code
        # and does not update phone number
        response = self.client.patch(url, data, HTTP_USER_AGENT=self.agent_android)
        self.user.refresh_from_db()

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        mocked_send_sms.assert_not_called()
        self.assertEqual(self.user.phone, original_phone)
        self.assertEqual(self.user.first_name, new_first_name)

    def test_changing_other_data_does_not_require_2fa(self):
        self.client.force_authenticate(self.user)
        url = reverse('user-detail', args=[self.user.pk])
        new_name = self.user.first_name + 'aaaaa'
        data = {
            'country': self.user.country,
            'first_name': new_name,
            'last_name': self.user.last_name,
            'phone': self.user.phone,
            'profile_photo': 'avatar.jpg',
        }

        response = self.client.patch(url, data)
        self.user.refresh_from_db()

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(self.user.first_name, new_name)

    @mock.patch.object(SendSmsThrottle, 'allow_request', return_value=True)
    @mock.patch('amuse.api.base.viewsets.user.send_sms_code')
    @mock.patch('amuse.vendor.twilio.sms.is_allowed_phone', return_value=('SE', True))
    def test_signup_requires_2fa_code(
        self, mocked_is_allowed, mocked_send_sms_code, mock_throttle
    ):
        UserViewSet.get_throttles = lambda x: []  # Disable SMS throttling
        # for unknown reason testcases start with 5 users
        user_count = User.objects.count()

        url = reverse('user-list')
        phone = '+46700000000'
        data = {
            'artist_name': 'data',
            'country': 'SE',
            'email': '2fa@example.com',
            'first_name': 'first',
            'language': 'en',
            'last_name': 'last',
            'password': 'blahonga',
            'phone': phone,
        }

        response = self.client.post(url, data)
        payload = response.json()

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(payload['phone'][0], 'Phone needs to be verifed')

        # Phone verify endpoint call
        verify_url = reverse('user-verify-phone')
        verify_data = {'phone': phone}
        response = self.client.post(verify_url, verify_data)
        otp_device = OtpDevice.objects.first()
        sms_code = otp_device._current_code()
        message = f'Your Amuse 2FA code is {sms_code[:3]} {sms_code[3:]}'

        self.assertEqual(OtpDevice.objects.count(), 1)
        self.assertFalse(otp_device.is_verified)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.json()['ErroMcErrorFace'], 'Computer says no')
        mocked_is_allowed.assert_called_once_with(phone)
        mocked_send_sms_code.assert_called_once_with(phone, message)

        # Invalid code sent does not trigger re-send of SMS
        mocked_is_allowed.reset_mock()
        mocked_send_sms_code.reset_mock()
        verify_data['sms_code'] = sms_code[:1]
        response = self.client.post(verify_url, verify_data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        mocked_send_sms_code.assert_not_called()
        mocked_is_allowed.assert_called_once_with(phone)
        self.assertEqual(response.json()['sms_code'], 'Invalid code')

        # Sending correct code sets OtpDevice to is_verified
        verify_data['sms_code'] = sms_code
        response = self.client.post(verify_url, verify_data)
        otp_device.refresh_from_db()

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(otp_device.is_verified)

        response = self.client.post(verify_url, verify_data)
        otp_device.refresh_from_db()

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(otp_device.is_verified)

        response = self.client.post(url, data)
        payload = response.json()
        user = User.objects.last()

        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.assertEqual(OtpDevice.objects.count(), 0)
        self.assertEqual(User.objects.count(), user_count + 1)
        self.assertEqual(user.phone, phone.replace(' ', ''))
        self.assertTrue(user.phone_verified)
        self.assertTrue(user.otp_enabled)

    @mock.patch('amuse.api.base.viewsets.user.send_sms_code')
    @mock.patch('amuse.vendor.twilio.sms.is_allowed_phone', return_value=('SE', True))
    def test_signup_multiple_otp_objects(self, mocked_is_allowed, mocked_send_sms_code):
        phone = '+4670 000 0000'
        OtpDevice.objects.create(phone=phone)
        OtpDevice.objects.create(phone=phone)

        url = reverse('user-list')

        data = {
            'artist_name': 'data',
            'country': 'SE',
            'email': '2fa@example.com',
            'first_name': 'first',
            'language': 'en',
            'last_name': 'last',
            'password': 'blahonga',
            'phone': phone,
        }

        self.assertEqual(OtpDevice.objects.count(), 2)
        response = self.client.post(url, data)

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(
            response.json()['OtpDeviceError'], 'Invalid number of OtpDevices'
        )

    @responses.activate
    @mock.patch.object(SendSmsThrottle, 'allow_request', return_value=True)
    def test_verify_phone_handles_twilio_exception(self, mock_sms_throttle):
        UserViewSet.get_throttles = lambda x: []
        responses.add(
            responses.GET,
            'https://lookups.twilio.com/v1/PhoneNumbers/+46700000000?Type=carrier',
            status=404,
            json={},
        )

        # Phone verify endpoint call
        verify_url = reverse('user-verify-phone')
        verify_data = {'phone': '+46700000000'}
        response = self.client.post(verify_url, verify_data)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.json()['phone'], 'Phone lookup failed')

    @mock.patch('amuse.api.base.viewsets.user.send_sms_code')
    @mock.patch(
        'amuse.api.base.viewsets.user.validate_phone', return_value='+46700000000'
    )
    def test_signup_sms_send_throttle(self, mocked_validate, mocked_send_sms_code):
        UserViewSet.get_throttles = lambda x: (SendSmsThrottle(),)

        url = reverse('user-verify-phone')
        data = {'phone': '+46700000000'}

        self.client.post(url, data)
        self.client.post(url, data)
        response = self.client.post(url, data)
        self.assertEqual(
            response.status_code, status.HTTP_429_TOO_MANY_REQUESTS, response.json()
        )

    @mock.patch('amuse.api.v5.serializers.user.send_sms_code')
    @mock.patch(
        'amuse.api.v5.serializers.user.validate_phone', return_value='+46700000000'
    )
    def test_update_phone_sms_throttle(self, mocked_validate, mocked_send_sms_code):
        UserViewSet.get_throttles = lambda x: (SendSmsThrottle(),)
        self.client.force_authenticate(self.user)
        url = reverse('user-detail', args=[self.user.pk])
        data = {
            'country': self.user.country,
            'first_name': self.user.first_name,
            'last_name': self.user.last_name,
            'phone': '+46700000000',
            'profile_photo': 'avatar.jpg',
        }

        self.client.patch(url, data)
        self.client.patch(url, data)
        response = self.client.patch(url, data)
        self.assertEqual(
            response.status_code, status.HTTP_429_TOO_MANY_REQUESTS, response.json()
        )

    @mock.patch('amuse.api.base.viewsets.user.LoginEndpointThrottle')
    @mock.patch('amuse.api.base.viewsets.user.send_sms_code')
    def test_email_login_2fa_sms_throttle(
        self, mocked_sms_send, mocked_login_throttler
    ):
        UserViewSet.get_throttles = lambda x: (SendSmsThrottle(),)
        mocked_login_throttler.return_value = mock.Mock(allow_request=lambda a, b: True)
        url = reverse('user-email')

        # No code passed sets code, sends sms and returns 403
        data = {'email': self.user.email, 'password': UserFactory.password}

        self.client.post(url, data, HTTP_USER_AGENT=self.agent_web)
        self.client.post(url, data, HTTP_USER_AGENT=self.agent_web)
        response = self.client.post(url, data, HTTP_USER_AGENT=self.agent_web)
        self.assertEqual(response.status_code, status.HTTP_429_TOO_MANY_REQUESTS)

    @mock.patch('amuse.api.base.viewsets.user.SendSmsThrottle')
    @mock.patch('amuse.api.base.viewsets.user.send_sms_code')
    @mock.patch('amuse.vendor.twilio.sms.is_allowed_phone', return_value=('SE', True))
    def test_verify_phone_multiple_otp_devices(
        self, mocked_is_allowed, mocked_send_sms_code, mock_sms_throttle
    ):
        phone = '+46700000000'
        OtpDevice.objects.create(phone=phone)
        OtpDevice.objects.create(phone=phone)
        url = reverse('user-verify-phone')

        response = self.client.post(url, {'phone': phone})

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.json()['ErroMcErrorFace'], 'Computer says no')

    @mock.patch('amuse.api.base.viewsets.user.SendSmsThrottle')
    @mock.patch('amuse.api.base.viewsets.user.send_sms_code')
    @mock.patch('amuse.vendor.twilio.sms.is_allowed_phone', return_value=('SE', True))
    def test_verify_phone_no_otp_devices(
        self, mocked_is_allowed, mocked_send_sms_code, mock_sms_throttle
    ):
        phone = '+46700000000'
        url = reverse('user-verify-phone')

        response = self.client.post(url, {'phone': phone})

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.json()['ErroMcErrorFace'], 'Computer says no')

    @mock.patch('amuse.api.base.viewsets.user.SendSmsThrottle')
    @mock.patch('amuse.api.base.viewsets.user.send_sms_code')
    @mock.patch('amuse.vendor.twilio.sms.is_allowed_phone', return_value=('SE', True))
    def test_verify_phone_one_otp_device(
        self, mocked_is_allowed, mocked_send_sms_code, mock_sms_throttle
    ):
        phone = '+46700000000'
        url = reverse('user-verify-phone')
        OtpDevice.objects.create(phone=phone)

        response = self.client.post(url, {'phone': phone})

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.json()['ErroMcErrorFace'], 'Computer says no')

    @override_switch("sinch:block-mismatch:se", True)
    def test_verify_phone_blocks_mismatched_countries(self):
        UserViewSet.get_throttles = lambda x: []
        url = reverse('user-verify-phone')
        phone = '+46700000000'
        response = self.client.post(url, {"phone": phone}, HTTP_CF_IPCOUNTRY="US")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    @override_switch("sinch:block-mismatch:se", True)
    @mock.patch('amuse.api.base.viewsets.user.SendSmsThrottle')
    @mock.patch('amuse.api.base.viewsets.user.send_sms_code')
    @mock.patch('amuse.vendor.twilio.sms.is_allowed_phone', return_value=('SE', True))
    def test_verify_phone_does_not_block_matching_countries(
        self, mocked_is_allowed, mocked_send_sms_code, mock_sms_throttle
    ):
        UserViewSet.get_throttles = lambda x: []
        url = reverse('user-verify-phone')
        phone = '+46700000000'
        response = self.client.post(url, {"phone": phone}, HTTP_CF_IPCOUNTRY="SE")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.json()['ErroMcErrorFace'], 'Computer says no')

    @override_switch("sinch:block-mismatch:se", True)
    @mock.patch('amuse.api.base.viewsets.user.SendSmsThrottle')
    @mock.patch('amuse.api.base.viewsets.user.send_sms_code')
    @mock.patch('amuse.vendor.twilio.sms.is_allowed_phone', return_value=('SE', True))
    def test_verify_phone_block_mismatch_countries_switch_is_disabled(
        self, mocked_is_allowed, mocked_send_sms_code, mock_sms_throttle
    ):
        UserViewSet.get_throttles = lambda x: []
        Switch.objects.filter(
            name="verify-phone-block-mismatch-countries:enabled"
        ).update(active=False)
        url = reverse('user-verify-phone')
        phone = '+46700000000'
        response = self.client.post(url, {"phone": phone}, HTTP_CF_IPCOUNTRY="US")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.json()['ErroMcErrorFace'], 'Computer says no')

    @responses.activate
    @mock.patch("amuse.api.base.viewsets.user.apple_authenticate")
    def test_apple_signup_does_not_require_2fa_or_phone(self, mock_apple_authenticate):
        user_count = User.objects.count()
        url = reverse('user-list')
        data = {
            'apple_signin_id': '123',
            'artist_name': 'data',
            'country': 'SE',
            'email': 'a@example.com',
            'first_name': 'first',
            'language': 'en',
            'last_name': 'last',
            'password': '',
        }

        response = self.client.post(url, data)
        user = User.objects.last()

        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.assertEqual(OtpDevice.objects.count(), 0)
        self.assertEqual(User.objects.count(), user_count + 1)
        self.assertFalse(user.phone_verified)
        self.assertFalse(user.otp_enabled)

    @override_switch("sinch:active:ww", active=True)
    @mock.patch.object(SendSmsThrottle, 'allow_request', return_value=True)
    @mock.patch('amuse.vendor.twilio.sms.is_allowed_phone', return_value=('SE', True))
    @mock.patch("amuse.api.base.viewsets.user.send_otp_sms")
    def test_verify_phone_uses_sinch_if_applicable(
        self, mock_send_otp_sms, mocked_is_allowed, mock_throttle
    ):
        url = reverse('user-verify-phone')
        data = {'phone': '+46701234567'}
        response = self.client.post(url, data)
        sms_code = OtpDevice.objects.first()._current_code()
        message = f'Your Amuse 2FA code is {sms_code[:3]} {sms_code[3:]}'

        mock_send_otp_sms.assert_called_once_with("+46701234567", message)

    @override_switch("sinch:active:ww", active=False)
    @mock.patch.object(SendSmsThrottle, 'allow_request', return_value=True)
    @mock.patch('amuse.vendor.twilio.sms.is_allowed_phone', return_value=('SE', True))
    @mock.patch("amuse.api.base.viewsets.user.send_sms_code")
    def test_verify_phone_uses_twilio_if_applicable(
        self, mock_send_otp_sms, mocked_is_allowed, mock_throttle
    ):
        url = reverse('user-verify-phone')
        data = {'phone': '+46701234567'}
        response = self.client.post(url, data)

        OtpDevice.objects.first()._current_code()
        sms_code = OtpDevice.objects.first()._current_code()
        message = f'Your Amuse 2FA code is {sms_code[:3]} {sms_code[3:]}'
        mock_send_otp_sms.assert_called_once_with("+46701234567", message)

    @override_switch("sinch:active:ww", active=True)
    @override_settings(ANDROID_APP_MFA_HASH='xyz-hash')
    @mock.patch.object(SendSmsThrottle, 'allow_request', return_value=True)
    @mock.patch('amuse.vendor.twilio.sms.is_allowed_phone', return_value=('SE', True))
    @mock.patch("amuse.api.base.viewsets.user.send_otp_sms")
    def test_verify_phone_uses_sinch_from_android(
        self, mock_send_otp_sms, mocked_is_allowed, mock_throttle
    ):
        url = reverse('user-verify-phone')
        data = {'phone': '+46701234567'}
        response = self.client.post(url, data, HTTP_USER_AGENT=self.agent_android)
        message = f'Your Amuse 2FA code is {OtpDevice.objects.first()._current_code()}\n\nxyz-hash'
        mock_send_otp_sms.assert_called_once_with("+46701234567", message)

    @override_switch("sinch:active:se", active=False)
    @override_settings(ANDROID_APP_MFA_HASH='xyz-hash')
    @mock.patch.object(SendSmsThrottle, 'allow_request', return_value=True)
    @mock.patch('amuse.vendor.twilio.sms.is_allowed_phone', return_value=('SE', True))
    @mock.patch("amuse.api.base.viewsets.user.send_sms_code")
    def test_verify_phone_uses_twilio_from_android(
        self, mock_send_otp_sms, mocked_is_allowed, mock_throttle
    ):
        url = reverse('user-verify-phone')
        data = {'phone': '+46701234567'}
        response = self.client.post(url, data, HTTP_USER_AGENT=self.agent_android)
        message = f'Your Amuse 2FA code is {OtpDevice.objects.first()._current_code()}\n\nxyz-hash'
        mock_send_otp_sms.assert_called_once_with("+46701234567", message)

    @mock.patch('amuse.api.base.viewsets.user.LoginEndpointThrottle')
    def test_email_login_fails_user_requested_delete(self, mock_throttler):
        mock_throttler.return_value = mock.Mock(allow_request=lambda a, b: True)
        url = reverse('user-email')

        user = UserFactory()
        UserMetadataFactory(
            user=user, is_delete_requested=True, delete_requested_at=datetime.now()
        )

        data = {'email': user.email, 'password': UserFactory.password}
        response = self.client.post(url, data, HTTP_USER_AGENT=self.agent_web)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.json()['email'], 'User is deleted')

    def test_user_requested_delete(self):
        UserMetadataFactory(
            user=self.user, is_delete_requested=False, delete_requested_at=None
        )
        self.client.force_authenticate(self.user)
        token = self.user.auth_token.key
        url = f'/api/users/delete/'
        response = self.client.delete(url)

        self.user.refresh_from_db()

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertTrue(self.user.usermetadata.is_delete_requested)
        self.assertIsNotNone(self.user.usermetadata.delete_requested_at)
        # Check that token is rotated
        self.assertNotEqual(token, self.user.auth_token.key)

    def test_user_requested_delete_unauthorized(self):
        UserMetadataFactory(
            user=self.user, is_delete_requested=False, delete_requested_at=None
        )
        url = f'/api/users/delete/'
        response = self.client.delete(url)

        self.user.refresh_from_db()

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertFalse(self.user.usermetadata.is_delete_requested)
        self.assertIsNone(self.user.usermetadata.delete_requested_at)

    def test_user_requested_delete_priority_user(self):
        self.user.category = User.CATEGORY_PRIORITY
        UserMetadataFactory(
            user=self.user, is_delete_requested=False, delete_requested_at=None
        )

        self.client.force_authenticate(self.user)
        url = f'/api/users/delete/'
        response = self.client.delete(url)

        self.user.refresh_from_db()
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertFalse(self.user.usermetadata.is_delete_requested)

    def test_user_requested_delete_locked_splits(self):
        UserMetadataFactory(
            user=self.user, is_delete_requested=False, delete_requested_at=None
        )
        self.royalty_split_1 = RoyaltySplitFactory(
            user=self.user,
            rate=1.0,
            start_date=None,
            end_date=None,
            status=RoyaltySplit.STATUS_CONFIRMED,
            is_locked=True,
        )

        self.client.force_authenticate(self.user)
        url = f'/api/users/delete/'
        response = self.client.delete(url)

        self.user.refresh_from_db()
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertFalse(self.user.usermetadata.is_delete_requested)

    def test_user_requested_delete_flagged_fraud_user(self):
        self.user.category = User.CATEGORY_FLAGGED
        UserMetadataFactory(
            user=self.user,
            is_delete_requested=False,
            delete_requested_at=None,
            flagged_reason=UserMetadata.FLAGGED_REASON_STREAMFARMER,
        )

        self.client.force_authenticate(self.user)
        url = f'/api/users/delete/'
        response = self.client.delete(url)

        self.user.refresh_from_db()
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertFalse(self.user.usermetadata.is_delete_requested)

    def test_user_requested_delete_flagged_non_fraud_user(self):
        self.user.category = User.CATEGORY_FLAGGED
        UserMetadataFactory(
            user=self.user,
            is_delete_requested=False,
            delete_requested_at=None,
            flagged_reason=UserMetadata.FLAGGED_REASON_RESTRICTED_COUNTRY,
        )

        self.client.force_authenticate(self.user)
        url = f'/api/users/delete/'
        response = self.client.delete(url)

        self.user.refresh_from_db()
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertTrue(self.user.usermetadata.is_delete_requested)

    def test_user_requested_delete_has_live_release(self):
        ReleaseFactory(user=self.user, status=Release.STATUS_RELEASED)
        UserMetadataFactory(
            user=self.user, is_delete_requested=False, delete_requested_at=None
        )

        self.client.force_authenticate(self.user)
        url = f'/api/users/delete/'
        response = self.client.delete(url)

        self.user.refresh_from_db()
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertFalse(self.user.usermetadata.is_delete_requested)

    def test_user_requested_delete_has_takendown_release(self):
        ReleaseFactory(user=self.user, status=Release.STATUS_TAKEDOWN)

        self.client.force_authenticate(self.user)
        url = f'/api/users/delete/'
        response = self.client.delete(url)

        self.user.refresh_from_db()
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertTrue(self.user.usermetadata.is_delete_requested)

    def test_user_requested_delete_pending_release_set_to_not_approved(self):
        release = ReleaseFactory(user=self.user, status=Release.STATUS_PENDING)

        self.client.force_authenticate(self.user)
        url = f'/api/users/delete/'
        response = self.client.delete(url)

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

        release.refresh_from_db()
        self.assertEqual(release.status, Release.STATUS_NOT_APPROVED)
