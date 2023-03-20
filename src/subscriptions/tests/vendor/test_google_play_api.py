import json
from base64 import b85encode
from unittest import mock

import httplib2
from django.test import TestCase, override_settings

from subscriptions.vendor.google.google_play_api import GooglePlayAPI, Error, HttpError

SAMPLE_SERVICE_ACCOUNT_KEY = {
    "type": "service_account",
    "project_id": "project-id",
    "private_key_id": "key-id",
    "private_key": "-----BEGIN PRIVATE KEY-----\nprivate-key\n-----END PRIVATE KEY-----\n",
    "client_email": "service-account-email",
    "client_id": "client-id",
    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
    "token_uri": "https://accounts.google.com/o/oauth2/token",
    "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
    "client_x509_cert_url": "https://www.googleapis.com/robot/v1/metadata/x509/service-account-email",
}

MOCK_SETTINGS = {
    'GOOGLE_PLAY_API_SERVICE_ACCOUNT': b85encode(
        json.dumps(SAMPLE_SERVICE_ACCOUNT_KEY).encode('utf-8')
    ).decode("utf-8"),
    'ANDROID_APP_PACKAGE': 'ANDROID.PACKAGE',
}


class MockBuildReturnValue(object):
    def __init__(self, cache_discovery=None, error=None, *args, **kwargs):
        self.return_value = {}
        self.error = error

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass

    def purchases(self):
        return self

    def subscriptions(self):
        return self

    def _create_return_val(self, packageName, subscriptionId, token):
        return {
            'package': packageName,
            'subscriptionId': subscriptionId,
            'token': token,
            'message': 'I am mock',
        }

    def get(self, packageName, subscriptionId, token):
        self.return_value = self._create_return_val(packageName, subscriptionId, token)
        return self

    def acknowledge(self, packageName, subscriptionId, token):
        self.return_value = self._create_return_val(packageName, subscriptionId, token)
        return self

    def revoke(self, packageName, subscriptionId, token):
        self.return_value = self._create_return_val(packageName, subscriptionId, token)
        return self

    def refund(self, packageName, subscriptionId, token):
        self.return_value = self._create_return_val(packageName, subscriptionId, token)
        return self

    def cancel(self, packageName, subscriptionId, token):
        self.return_value = self._create_return_val(packageName, subscriptionId, token)
        return self

    def defer(self, packageName, subscriptionId, token, body):
        self.return_value = self._create_return_val(packageName, subscriptionId, token)
        return self

    def execute(self):
        if self.error:
            raise self.error
        return self.return_value


@override_settings(**MOCK_SETTINGS)
class TestVerifyPurchaseToken(TestCase):
    @mock.patch('google.oauth2.service_account.Credentials.from_service_account_info')
    @mock.patch('subscriptions.vendor.google.google_play_api.build')
    def test_ensure_verify_purchase_is_executed(self, mock_build, mock_credentials):
        mock_credentials.return_value = {}
        mock_build.return_value = MockBuildReturnValue()
        actual_result = GooglePlayAPI().verify_purchase_token(123, 'sku', 'token')

        self.assertEqual(
            actual_result,
            {
                'package': 'ANDROID.PACKAGE',
                'subscriptionId': 'sku',
                'token': 'token',
                'message': 'I am mock',
            },
        )

    @mock.patch('google.oauth2.service_account.Credentials.from_service_account_info')
    @mock.patch('subscriptions.vendor.google.google_play_api.build')
    @mock.patch('subscriptions.vendor.google.google_play_api.warning')
    def test_ensure_failed_request_returns_none(
        self, mock_warning, mock_build, mock_credentials
    ):
        mock_credentials.return_value = {}
        mock_build.return_value = MockBuildReturnValue(error=Error('mock error'))
        actual_result = GooglePlayAPI().verify_purchase_token('123', 'sku', 'token')

        mock_warning.assert_called_once_with(
            '123',
            'Unable to verify purchase token, token=token, subscriptionId=sku, error="mock error"',
        )
        self.assertIsNone(actual_result)


@override_settings(**MOCK_SETTINGS)
class TestAcknowledge(TestCase):
    @mock.patch('google.oauth2.service_account.Credentials.from_service_account_info')
    @mock.patch('subscriptions.vendor.google.google_play_api.build')
    def test_ensure_verify_purchase_is_executed(self, mock_build, mock_credentials):
        mock_credentials.return_value = {}
        mock_build.return_value = MockBuildReturnValue()
        actual_result = GooglePlayAPI().acknowledge(123, 'sku', 'token')

        self.assertEqual(
            actual_result,
            {
                'package': 'ANDROID.PACKAGE',
                'subscriptionId': 'sku',
                'token': 'token',
                'message': 'I am mock',
            },
        )

    @mock.patch('google.oauth2.service_account.Credentials.from_service_account_info')
    @mock.patch('subscriptions.vendor.google.google_play_api.build')
    @mock.patch('subscriptions.vendor.google.google_play_api.warning')
    def test_ensure_failed_request_returns_none(
        self, mock_warning, mock_build, mock_credentials
    ):
        mock_credentials.return_value = {}
        mock_build.return_value = MockBuildReturnValue(error=Error('mock error'))
        actual_result = GooglePlayAPI().acknowledge('123', 'sku', 'token')

        mock_warning.assert_called_once_with(
            '123',
            'Unable to acknowledge purchase, token=token, subscriptionId=sku, error="mock error"',
        )
        self.assertIsNone(actual_result)


@override_settings(**MOCK_SETTINGS)
class TestCancel(TestCase):
    @mock.patch('google.oauth2.service_account.Credentials.from_service_account_info')
    @mock.patch('subscriptions.vendor.google.google_play_api.build')
    def test_ensure_refund_is_executed(self, mock_build, mock_credentials):
        mock_credentials.return_value = {}
        mock_build.return_value = MockBuildReturnValue()
        actual_result = GooglePlayAPI().cancel(123, 'sku', 'token')

        self.assertEqual(actual_result, {'success': True, 'message': ''})

    @mock.patch('google.oauth2.service_account.Credentials.from_service_account_info')
    @mock.patch('subscriptions.vendor.google.google_play_api.build')
    @mock.patch('subscriptions.vendor.google.google_play_api.warning')
    def test_ensure_failed_request_returns_none(
        self, mock_warning, mock_build, mock_credentials
    ):
        mock_credentials.return_value = {}
        mock_build.return_value = MockBuildReturnValue(
            error=HttpError(
                httplib2.Response({"status": 500}),
                b'{"error": {"message": "Mock Error" }}',
            )
        )
        actual_result = GooglePlayAPI().cancel('123', 'sku', 'token')

        mock_warning.assert_called_once()

        self.assertIsInstance(actual_result, dict)
        self.assertIn('success', actual_result)


@override_settings(**MOCK_SETTINGS)
class TestRefund(TestCase):
    @mock.patch('google.oauth2.service_account.Credentials.from_service_account_info')
    @mock.patch('subscriptions.vendor.google.google_play_api.build')
    def test_ensure_refund_is_executed(self, mock_build, mock_credentials):
        mock_credentials.return_value = {}
        mock_build.return_value = MockBuildReturnValue()
        actual_result = GooglePlayAPI().refund(123, 'sku', 'token')

        self.assertEqual(actual_result, {'success': True, 'message': ''})

    @mock.patch('google.oauth2.service_account.Credentials.from_service_account_info')
    @mock.patch('subscriptions.vendor.google.google_play_api.build')
    @mock.patch('subscriptions.vendor.google.google_play_api.warning')
    def test_ensure_failed_request_returns_none(
        self, mock_warning, mock_build, mock_credentials
    ):
        mock_credentials.return_value = {}
        mock_build.return_value = MockBuildReturnValue(
            error=HttpError(
                httplib2.Response({"status": 500}),
                b'{"error": {"message": "Mock Error" }}',
            )
        )
        actual_result = GooglePlayAPI().refund('123', 'sku', 'token')

        mock_warning.assert_called_once()

        self.assertIsInstance(actual_result, dict)
        self.assertIn('success', actual_result)


@override_settings(**MOCK_SETTINGS)
class TestRevoke(TestCase):
    @mock.patch('google.oauth2.service_account.Credentials.from_service_account_info')
    @mock.patch('subscriptions.vendor.google.google_play_api.build')
    def test_ensure_revoke_is_executed(self, mock_build, mock_credentials):
        mock_credentials.return_value = {}
        mock_build.return_value = MockBuildReturnValue()
        actual_result = GooglePlayAPI().revoke(123, 'sku', 'token')

        self.assertEqual(actual_result, {'success': True, 'message': ''})

    @mock.patch('google.oauth2.service_account.Credentials.from_service_account_info')
    @mock.patch('subscriptions.vendor.google.google_play_api.build')
    @mock.patch('subscriptions.vendor.google.google_play_api.warning')
    def test_ensure_failed_request_returns_none(
        self, mock_warning, mock_build, mock_credentials
    ):
        mock_credentials.return_value = {}
        mock_build.return_value = MockBuildReturnValue(
            error=HttpError(
                httplib2.Response({"status": 500}),
                b'{"error": {"message": "Mock Error" }}',
            )
        )
        actual_result = GooglePlayAPI().revoke('123', 'sku', 'token')

        mock_warning.assert_called_once()

        self.assertIsInstance(actual_result, dict)
        self.assertIn('success', actual_result)


@override_settings(**MOCK_SETTINGS)
class TestDeferr(TestCase):
    @mock.patch('google.oauth2.service_account.Credentials.from_service_account_info')
    @mock.patch('subscriptions.vendor.google.google_play_api.build')
    def test_ensure_defer_is_executed(self, mock_build, mock_credentials):
        mock_credentials.return_value = {}
        mock_build.return_value = MockBuildReturnValue()
        actual_result = GooglePlayAPI().defer(123, 'sku', 'token', '', '')

        self.assertEqual(actual_result, {'success': True, 'message': ''})

    @mock.patch('google.oauth2.service_account.Credentials.from_service_account_info')
    @mock.patch('subscriptions.vendor.google.google_play_api.build')
    @mock.patch('subscriptions.vendor.google.google_play_api.warning')
    def test_ensure_failed_request_returns_none(
        self, mock_warning, mock_build, mock_credentials
    ):
        mock_credentials.return_value = {}
        mock_build.return_value = MockBuildReturnValue(
            error=HttpError(
                httplib2.Response({"status": 500}),
                b'{"error": {"message": "Mock Error" }}',
            )
        )
        actual_result = GooglePlayAPI().defer('123', 'sku', 'token', '', '')

        mock_warning.assert_called_once()

        self.assertIsInstance(actual_result, dict)
        self.assertIn('success', actual_result)
