from unittest.mock import patch
from amuse.tests.test_api.base import AmuseAPITestCase
from users.tests.factories import UserFactory
from users.models.user import OtpDevice
from django.urls import reverse
from amuse.tests.cookie_factory import generate_test_client_otp_cookie
from rest_framework.test import APIClient
from django.conf import settings
from django.core.signing import get_cookie_signer
from django.utils.module_loading import import_string


class TestOtpTestCase(AmuseAPITestCase):
    def setUp(self):
        self.path = reverse("related-users")
        self.test_user = UserFactory()
        self.client.cookies = generate_test_client_otp_cookie(self.test_user.pk)

    @patch('amuse.api.base.views.otp.send_otp_code')
    def test_otp_trigger_sms_success(self, mock_func):
        mock_func.return_value = True
        path = reverse('otp-trigger')
        response = self.client.get(path)
        data = response.json()
        self.assertTrue(data['success'])
        self.assertEqual(response.status_code, 200)

    @patch('amuse.api.base.views.otp.send_otp_code')
    def test_otp_trigger_sms_failed(self, mock_func):
        mock_func.return_value = False
        path = reverse('otp-trigger')
        response = self.client.get(path)
        data = response.json()
        self.assertFalse(data['success'])
        self.assertEqual(response.status_code, 400)

    @patch('amuse.api.base.views.otp.send_otp_code')
    def test_otp_trigger_sms_throttling(self, mock_func):
        mock_func.return_value = True
        user = UserFactory()
        client = self.client
        client.cookies = generate_test_client_otp_cookie(user.pk)
        path = reverse('otp-trigger')
        hit_throttling = False
        for i in range(1, 5):
            response = client.get(path)
            if response.status_code == 429:
                hit_throttling = True
                break
        assert hit_throttling == True

    @patch('amuse.api.base.views.otp.send_otp_code')
    def test_trigger_sms_and_verify_flow(self, mock_func):
        mock_func.return_value = True
        user = UserFactory()
        client = self.client
        client.cookies = generate_test_client_otp_cookie(user.pk)
        path = reverse('otp-trigger')
        response = client.get(path)
        assert response.status_code == 200

        # Extract sms_code from OtpDevice table
        otp = OtpDevice.objects.get_unique_otp_device(user=user)
        code = otp._current_code()

        # Call /otp/verify
        verify_path = reverse('otp-verify', kwargs={'otp_id': otp.pk})
        verify_response = client.post(verify_path, data={'sms_code': code})
        data = verify_response.json()
        self.assertEqual(data['success'], True)
        self.assertEqual(data['user']['id'], user.pk)

        # Assert DB values are correct
        user.refresh_from_db()
        otp.refresh_from_db()
        self.assertTrue(user.phone_verified)
        self.assertTrue(user.otp_enabled)
        self.assertTrue(otp.is_verified)

        # Assert we set correct cookies in response
        access_cookie = verify_response.cookies.get(settings.ACCESS_COOKIE_NAME)
        refresh_cookie = verify_response.cookies.get(settings.REFRESH_COOKIE_NAME)
        token_generator_klazz = import_string(settings.AUTH_TOKEN_GENERATOR_CLASS)
        access_token = get_cookie_signer(salt=settings.ACCESS_COOKIE_NAME).unsign(
            access_cookie.value
        )
        refresh_token = get_cookie_signer(salt=settings.REFRESH_COOKIE_NAME).unsign(
            refresh_cookie.value
        )
        assert token_generator_klazz.get_user_id(access_token) == user.pk
        assert token_generator_klazz.get_user_id(refresh_token) == user.pk

        # Second call to /otp/verify for same otp code will return 400 since
        # counter is updated after first verification
        verify_response = client.post(verify_path, data={'sms_code': code})
        data = verify_response.json()
        self.assertEqual(data['success'], False)
        self.assertEqual(verify_response.status_code, 400)

    def test_verify_otp_device_does_not_exist(self):
        user = UserFactory()
        client = self.client
        client.cookies = generate_test_client_otp_cookie(user.pk)
        verify_path = reverse('otp-verify', kwargs={'otp_id': 1000})
        verify_response = client.post(verify_path, data={'sms_code': '123456'})
        data = verify_response.json()
        self.assertEqual(data['success'], False)
        self.assertEqual(data['errors'][0], f"OTP device with id 1000 does not exist")

    @patch('amuse.api.base.views.otp.send_otp_code')
    def test_otp_trigger_missing_cookie(self, mock_func):
        mock_func.return_value = True
        client = APIClient()
        path = reverse('otp-trigger')
        response = client.get(path)
        self.assertEqual(response.status_code, 403)
        assert response.json()['code'] == 'missing-token'

    @patch('amuse.api.base.views.otp.send_otp_code')
    def test_otp_trigger_user_deactivated(self, mock_func):
        mock_func.return_value = True
        user = UserFactory(is_active=False)
        client = APIClient()
        client.cookies = generate_test_client_otp_cookie(user.pk)
        path = reverse('otp-trigger')
        response = client.get(path)
        data = response.json()
        self.assertEqual(response.status_code, 403)
        self.assertEqual(data['code'], 'user-deactivated')

    def test_verify_missing_cookie(self):
        client = APIClient()
        verify_path = reverse('otp-verify', kwargs={'otp_id': 1000})
        verify_response = client.post(verify_path, data={'sms_code': '123456'})
        data = verify_response.json()
        self.assertEqual(verify_response.status_code, 403)
        assert data['code'] == 'missing-token'

    def test_verify_otp_device_invalid_otp_id(self):
        test_params = ['a', '%5Cu00BD', '%34']
        user = UserFactory()
        client = self.client
        client.cookies = generate_test_client_otp_cookie(user.pk)
        for param in test_params:
            verify_path = reverse('otp-verify', kwargs={'otp_id': param})
            verify_response = client.post(verify_path, data={'sms_code': '123456'})
            self.assertEqual(verify_response.status_code, 400)
            self.assertEqual(verify_response.json()["otp_id"], 'Input value is invalid')
