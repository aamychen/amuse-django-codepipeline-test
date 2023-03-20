from unittest import mock
from rest_framework.exceptions import ValidationError
from django.test import TestCase
from rest_framework.test import APIRequestFactory
from amuse.api.helpers import (
    send_login_succeeded,
    is_2fa_enabled_for_client,
    is_2fa_enabled,
)
from users.tests.factories import UserFactory
from waffle.testutils import override_flag


class TestSendLoginSucceeded(TestCase):
    @mock.patch('amuse.tasks.zendesk_create_or_update_user')
    @mock.patch('amuse.api.helpers.generate_password_reset_url', return_value='url.com')
    @mock.patch('amuse.api.helpers.login_succeeded')
    def test_login_succeeded(self, mock_login_succeeded, _, __):
        user = UserFactory()
        headers = {
            'HTTP_X_FORWARDED_FOR': '123.123.123.432',
            'HTTP_USER_AGENT': 'amuse-iOS/4.1.0; WiFi',
            'HTTP_CF_IPCOUNTRY': 'SE',
        }
        request = APIRequestFactory().post("", **headers)
        send_login_succeeded(request, user)
        mock_login_succeeded.assert_called_once_with(
            user,
            {
                'country': 'SE',
                'ip': '123.123.123.432',
                'device_family': 'Other',
                'os_family': 'iOS',
                'user_agent_family': 'Amuse for iOS',
                'url': 'url.com',
            },
        )


class TestIs2faEnabledForClient(TestCase):
    def test_is_2fa_enabled_for_client(self):
        tests = [
            {'client': 'web', 'mfa_enabled': True},
            {'client': 'iOS', 'mfa_enabled': True},
            {'client': 'android', 'mfa_enabled': True},
            {'client': 'other', 'mfa_enabled': True},
            {'client': 'web', 'mfa_enabled': False},
            {'client': 'iOS', 'mfa_enabled': False},
            {'client': 'android', 'mfa_enabled': False},
            {'client': 'other', 'mfa_enabled': False},
        ]

        for test in tests:
            mfa_enabled = test['mfa_enabled']
            client = test['client']
            msg = f'Should be {"Enabled" if mfa_enabled else "Disabled"} for {client}'

            with self.subTest(msg):
                with override_flag(name=f'2FA-{client.lower()}', active=mfa_enabled):
                    headers = {'HTTP_USER_AGENT': f'amuse-{client}/4.1.0; WiFi'}
                    request = APIRequestFactory().post("", **headers)

                    actual = is_2fa_enabled_for_client(request)
                    self.assertEqual(actual, mfa_enabled)


class TestIs2FaEnabled(TestCase):
    @mock.patch('amuse.tasks.zendesk_create_or_update_user')
    def test_if_apple_social_user_return_false(self, _):
        user = UserFactory(apple_signin_id='xyz')
        request = APIRequestFactory().post("")
        actual = is_2fa_enabled(request, user)
        self.assertFalse(actual)

    @mock.patch('amuse.api.helpers.is_2fa_enabled_for_client', return_value=False)
    @mock.patch('amuse.tasks.zendesk_create_or_update_user')
    def test_if_mfa_disabled_for_client_return_false(self, _, __):
        user = UserFactory()
        actual = is_2fa_enabled(APIRequestFactory().post(""), user)
        self.assertFalse(actual)

    @mock.patch('amuse.api.helpers.is_2fa_enabled_for_client', return_value=True)
    @mock.patch('amuse.tasks.zendesk_create_or_update_user')
    def test_if_otp_disaled_return_false(self, _, __):
        user = UserFactory(otp_enabled=False)
        actual = is_2fa_enabled(APIRequestFactory().post(""), user)
        self.assertFalse(actual)

    @mock.patch('amuse.api.helpers.is_2fa_enabled_for_client', return_value=True)
    @mock.patch('amuse.tasks.zendesk_create_or_update_user')
    def test_mfa_enabled_success(self, _, __):
        user = UserFactory(otp_enabled=True, phone='123456789')
        actual = is_2fa_enabled(APIRequestFactory().post(""), user)
        self.assertTrue(actual)

    @mock.patch('amuse.api.helpers.is_2fa_enabled_for_client', return_value=True)
    @mock.patch('amuse.tasks.zendesk_create_or_update_user')
    def test_if_phone_missing_raise_validation_error(self, _, __):
        user = UserFactory(otp_enabled=True, phone='')
        with self.assertRaises(ValidationError):
            is_2fa_enabled(APIRequestFactory().post(""), user)
