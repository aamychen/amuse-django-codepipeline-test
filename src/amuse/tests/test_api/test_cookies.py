from unittest.mock import patch
from django.test import TestCase
from users.tests.factories import UserFactory
from rest_framework.response import Response
from rest_framework.request import HttpRequest
from amuse.api.base.cookies import set_otp_cookie, set_access_cookie, set_refresh_cookie
from django.conf import settings


class TestCookiesTestCase(TestCase):
    @patch('amuse.tasks.zendesk_create_or_update_user')
    def setUp(self, mock) -> None:
        self.user = UserFactory()
        self.response = Response()
        self.request = HttpRequest()

    def test_set_otp_cookie(self):
        response = self.response
        set_otp_cookie(response, self.user.pk)
        cookie = response.cookies.get(settings.OTP_COOKIE_NAME)

        assert cookie.key == settings.OTP_COOKIE_NAME
        assert cookie.value is not None

    def test_set_access_cookie(self):
        response = self.response
        set_access_cookie(response, self.user.pk)
        cookie = response.cookies.get(settings.ACCESS_COOKIE_NAME)

        assert cookie.key == settings.ACCESS_COOKIE_NAME
        assert cookie.value is not None

    def test_set_refresh_cookie(self):
        response = self.response
        set_refresh_cookie(response, self.user.pk)
        cookie = response.cookies.get(settings.REFRESH_COOKIE_NAME)

        assert cookie.key == settings.REFRESH_COOKIE_NAME
        assert cookie.value is not None
