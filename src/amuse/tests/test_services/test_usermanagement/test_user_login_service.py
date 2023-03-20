from datetime import datetime
from unittest import mock

import responses
from django.test import TestCase
from rest_framework.test import APIRequestFactory

from amuse.services.usermanagement import UserLoginService
from amuse.services.usermanagement.signin_handlers import (
    EmailSignInHandler,
    GoogleSignInHandler,
    AppleSignInHandler,
    FacebookSignInHandler,
)
from users.tests.factories import (
    UserFactory,
    UserMetadataFactory,
    UserArtistRoleFactory,
    Artistv2Factory,
)

SERVICE_PATH = 'amuse.services.usermanagement.user_login_service'


class TestUserLoginServiceFlow(TestCase):
    @mock.patch('amuse.tasks.zendesk_create_or_update_user')
    def setUp(self, _):
        self.user = UserFactory(spotify_id='spotify')

        UserArtistRoleFactory(
            user=self.user,
            artist=Artistv2Factory(owner=self.user, spotify_id=self.user.spotify_id),
        )

        self.request = APIRequestFactory().request()

    @responses.activate
    def test_email_successful(self):
        response = UserLoginService().email(
            self.request, self.user.email, UserFactory.password
        )

        self.assertIsNotNone(response)
        self.assertEqual(response.status_code, 200)

    @responses.activate
    def test_return_403_if_credentials_are_wrong(self):
        response = UserLoginService().email(self.request, self.user.email, 'invalid')

        self.assertIsNotNone(response)
        self.assertEqual(response.status_code, 403)

    @responses.activate
    def test_return_400_if_user_requested_delete(self):
        UserMetadataFactory(
            user=self.user, is_delete_requested=True, delete_requested_at=datetime.now()
        )

        response = UserLoginService().email(
            self.request, self.user.email, UserFactory.password
        )

        self.assertIsNotNone(response)
        self.assertEqual(response.status_code, 400)

    @mock.patch(f'{SERVICE_PATH}.refresh_spotify_artist_images.delay')
    @mock.patch(f'{SERVICE_PATH}.send_login_succeeded')
    @mock.patch(f'{SERVICE_PATH}.set_refresh_cookie')
    @mock.patch(f'{SERVICE_PATH}.set_access_cookie')
    @mock.patch(f'{SERVICE_PATH}.set_otp_cookie')
    @mock.patch(f'{SERVICE_PATH}.is_2fa_enabled', return_value=True)
    def test_return_ok_if_mfa_enabled(
        self,
        _,
        mock_set_otp_cookie,
        mock_set_access_cookie,
        mock_set_refresh_cookie,
        mock_send_login_succeeded,
        mock_refresh_spotify_images,
    ):
        response = UserLoginService().email(
            self.request, self.user.email, UserFactory.password
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(1, mock_set_otp_cookie.call_count)
        self.assertEqual(0, mock_set_access_cookie.call_count)
        self.assertEqual(0, mock_set_refresh_cookie.call_count)
        self.assertEqual(1, mock_send_login_succeeded.call_count)
        self.assertEqual(1, mock_refresh_spotify_images.call_count)


class TestUserLoginServiceExecutesProperHandler(TestCase):
    def setUp(self):
        self.request = APIRequestFactory().request()

    @responses.activate
    @mock.patch.object(EmailSignInHandler, 'authenticate')
    def test_email_handler(self, mock_handler):
        UserLoginService().email(self.request, '', '')

        mock_handler.assert_called_once_with(self.request)

    @responses.activate
    @mock.patch.object(GoogleSignInHandler, 'authenticate')
    def test_google_handler(self, mock_handler):
        UserLoginService().google(self.request, '', '')

        mock_handler.assert_called_once_with(self.request)

    @responses.activate
    @mock.patch.object(AppleSignInHandler, 'authenticate')
    def test_apple_handler(self, mock_handler):
        UserLoginService().apple(self.request, '', '')

        mock_handler.assert_called_once_with(self.request)

    @responses.activate
    @mock.patch.object(FacebookSignInHandler, 'authenticate')
    def test_facebook_handler(self, mock_handler):
        UserLoginService().facebook(self.request, '', '')

        mock_handler.assert_called_once_with(self.request)


class TestUserLoginServiceSocialLogin(TestCase):
    def setUp(self):
        self.request = APIRequestFactory().request()

    @responses.activate
    @mock.patch.object(UserLoginService, 'apple')
    def test_apple_social_login(self, mock_method):
        validated_data = {'access_token': '123', 'apple_signin_id': 'abc'}
        UserLoginService().social_login(self.request, 'apple', validated_data)

        mock_method.assert_called_once_with(self.request, '123', 'abc')

    @responses.activate
    @mock.patch.object(UserLoginService, 'google')
    def test_google_social_login(self, mock_method):
        validated_data = {'google_id': '123', 'google_id_token': 'abc'}
        UserLoginService().social_login(self.request, 'google', validated_data)

        mock_method.assert_called_once_with(self.request, '123', 'abc')

    @responses.activate
    @mock.patch.object(UserLoginService, 'facebook')
    def test_facebook_social_login(self, mock_method):
        validated_data = {'facebook_id': '123', 'facebook_access_token': 'abc'}
        UserLoginService().social_login(self.request, 'facebook', validated_data)

        mock_method.assert_called_once_with(self.request, '123', 'abc')

    @responses.activate
    def test_invalid_social_login(self):
        with self.assertRaises(ValueError):
            UserLoginService().social_login(self.request, 'x', {})
