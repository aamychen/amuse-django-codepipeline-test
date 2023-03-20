from unittest.mock import patch
from django.test import TestCase
from users.tests.factories import UserFactory
from rest_framework.response import Response
from rest_framework.request import HttpRequest
from amuse.tokens import otp_token_generator
from amuse.tests.cookie_factory import (
    generate_test_client_otp_cookie,
    generate_test_client_access_cookie,
    generate_test_client_refresh_cookie,
)
from django.test import RequestFactory
from rest_framework.exceptions import AuthenticationFailed
from amuse.api.base.authentication import (
    authenticate_from_otp_cookie,
    JWTCookieAuthentication,
)


class TestJWTCookieAuthenticationTestCase(TestCase):
    @patch('amuse.tasks.zendesk_create_or_update_user')
    def setUp(self, mock) -> None:
        self.user = UserFactory()
        self.response = Response()
        self.request = HttpRequest()

    @patch('rest_framework.request.HttpRequest.get_signed_cookie')
    def test_authenticate_from_otp_cookie(self, mock_fnc):
        mock_fnc.return_value = otp_token_generator.make_token(self.user.pk)
        request = self.request
        u = authenticate_from_otp_cookie(request)
        assert u.pk == self.user.pk

    @patch('rest_framework.request.HttpRequest.get_signed_cookie')
    def test_authenticate_from_otp_cookie_failed(self, mock_fnc):
        mock_fnc.return_value = "wrong-value"
        request = self.request
        u = authenticate_from_otp_cookie(request)
        assert u is None

    @patch('rest_framework.request.HttpRequest.get_signed_cookie')
    def test_authenticate_from_otp_cookie_user_not_found(self, mock_fnc):
        mock_fnc.return_value = otp_token_generator.make_token(user_id=1000000000)
        request = self.request
        u = authenticate_from_otp_cookie(request)
        assert u is None

    def test_authenticate_from_access_cookie(self):
        request = RequestFactory()
        request.cookies = generate_test_client_access_cookie(user_id=self.user.pk)
        u, t = JWTCookieAuthentication().authenticate(request.request())
        assert u.pk == self.user.pk

    def test_authenticate_from_access_cookie_missing_user(self):
        request = RequestFactory()
        request.cookies = generate_test_client_access_cookie(user_id=1000000000)
        with self.assertRaises(AuthenticationFailed):
            JWTCookieAuthentication().authenticate(request.request())

    def test_authenticate_from_access_cookie_missing_cookie(self):
        request = RequestFactory()
        assert JWTCookieAuthentication().authenticate(request.request()) is None

    def test_authenticate_from_access_cookie_wrong_token(self):
        request = RequestFactory()
        request.cookies = generate_test_client_refresh_cookie(user_id=self.user.pk)
        assert JWTCookieAuthentication().authenticate(request.request()) is None

    def test_authenticate_from_access_cookie_user_deactivated(self):
        user = UserFactory(is_active=False)
        request = RequestFactory()
        request.cookies = generate_test_client_access_cookie(user_id=user.id)
        with self.assertRaises(AuthenticationFailed):
            JWTCookieAuthentication().authenticate(request.request())
