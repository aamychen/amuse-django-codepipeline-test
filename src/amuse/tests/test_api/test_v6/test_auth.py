from datetime import datetime
from unittest import mock

from django.core.cache import cache
from django.test import override_settings
from django.urls import reverse
from rest_framework import status

from amuse.tests.test_api.base import API_V6_ACCEPT_VALUE, AmuseAPITestCase
from users.tests.factories import (
    UserFactory,
    UserMetadataFactory,
    Artistv2Factory,
    UserArtistRoleFactory,
)

SERVICE_PATH = 'amuse.services.usermanagement.user_login_service'


class TestLoginAPIV6TestCase(AmuseAPITestCase):
    @mock.patch('amuse.tasks.zendesk_create_or_update_user')
    def setUp(self, _):
        self.url = reverse('auth-login')
        self.user = UserFactory(
            phone_verified=True, otp_enabled=True, apple_signin_id='fake-apple-123'
        )

        UserArtistRoleFactory(
            user=self.user,
            artist=Artistv2Factory(owner=self.user, spotify_id=self.user.spotify_id),
        )

        self.client.credentials(HTTP_ACCEPT=API_V6_ACCEPT_VALUE)
        cache.clear()

    @override_settings(GOOGLE_CAPTCHA_ENABLED=True)
    @mock.patch('amuse.tasks.zendesk_create_or_update_user')
    def test_if_invalid_google_captcha_raise_error(self, _):
        data = {'email': self.user.email, 'password': UserFactory.password}
        response = self.client.post(self.url, data)
        self.assertEqual(
            response.status_code, status.HTTP_400_BAD_REQUEST, response.data
        )

    @mock.patch('amuse.api.base.views.auth.LoginEndpointThrottle')
    def test_if_username_incorrect_return_403(self, mock_throttler):
        mock_throttler.return_value = mock.Mock(allow_request=lambda a, b: True)

        data = {'email': 'invalid@email.com', 'password': 'fake'}
        response = self.client.post(self.url, data)

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    @mock.patch('amuse.api.base.viewsets.user.LoginEndpointThrottle')
    def test_if_user_requested_delete_return_400(self, mock_throttler):
        mock_throttler.return_value = mock.Mock(allow_request=lambda a, b: True)

        UserMetadataFactory(
            user=self.user, is_delete_requested=True, delete_requested_at=datetime.now()
        )

        data = {'email': self.user.email, 'password': UserFactory.password}
        response = self.client.post(self.url, data)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.json()['email'], 'User is deleted')

    @mock.patch(f'{SERVICE_PATH}.refresh_spotify_artist_images.delay')
    @mock.patch(f'{SERVICE_PATH}.send_login_succeeded')
    @mock.patch(f'{SERVICE_PATH}.set_refresh_cookie')
    @mock.patch(f'{SERVICE_PATH}.set_access_cookie')
    @mock.patch(f'{SERVICE_PATH}.set_otp_cookie')
    @mock.patch(f'{SERVICE_PATH}.is_2fa_enabled', return_value=True)
    def test_if_mfa_enabled_return_ok(
        self,
        _,
        mock_set_otp_cookie,
        mock_set_access_cookie,
        mock_set_refresh_cookie,
        mock_send_login_succeeded,
        mock_refresh_spotify_images,
    ):
        data = {'email': self.user.email, 'password': UserFactory.password}
        response = self.client.post(self.url, data)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(1, mock_set_otp_cookie.call_count)
        self.assertEqual(0, mock_set_access_cookie.call_count)
        self.assertEqual(0, mock_set_refresh_cookie.call_count)
        self.assertEqual(1, mock_send_login_succeeded.call_count)
        self.assertEqual(1, mock_refresh_spotify_images.call_count)

    @mock.patch(f'{SERVICE_PATH}.refresh_spotify_artist_images.delay')
    @mock.patch(f'{SERVICE_PATH}.send_login_succeeded')
    @mock.patch(f'{SERVICE_PATH}.set_refresh_cookie')
    @mock.patch(f'{SERVICE_PATH}.set_access_cookie')
    @mock.patch(f'{SERVICE_PATH}.set_otp_cookie')
    @mock.patch(f'{SERVICE_PATH}.is_2fa_enabled', return_value=False)
    def test_if_mfa_disabled_return_ok(
        self,
        _,
        mock_set_otp_cookie,
        mock_set_access_cookie,
        mock_set_refresh_cookie,
        mock_send_login_succeeded,
        mock_refresh_spotify_images,
    ):
        data = {'email': self.user.email, 'password': UserFactory.password}
        response = self.client.post(self.url, data)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(0, mock_set_otp_cookie.call_count)
        self.assertEqual(1, mock_set_access_cookie.call_count)
        self.assertEqual(1, mock_set_refresh_cookie.call_count)
        self.assertEqual(1, mock_send_login_succeeded.call_count)
        self.assertEqual(1, mock_refresh_spotify_images.call_count)


class TestLoginApiVersionsCase(AmuseAPITestCase):
    @mock.patch('amuse.tasks.zendesk_create_or_update_user')
    def test_if_not_v6_return_api_version_not_supported_error(self, _):
        user = UserFactory()
        data = {'email': user.email, 'password': UserFactory.password}

        for i in range(1, 8):
            request_version = f'application/json; version={i}'
            with self.subTest():
                cache.clear()
                self.client.credentials(HTTP_ACCEPT=request_version)

                response = self.client.post(reverse('auth-login'), data)
                if request_version == API_V6_ACCEPT_VALUE:
                    self.assertEqual(response.status_code, status.HTTP_200_OK)
                else:
                    self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
                    self.assertEqual(
                        response.json()['detail'], 'API version is not supported.'
                    )
