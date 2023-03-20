from unittest.mock import patch

from django.conf import settings
from django.test import TestCase, override_settings
from rest_framework.exceptions import ValidationError
from rest_framework.test import APIRequestFactory
from amuse.permissions import ReCaptchaPermission


@override_settings(GOOGLE_CAPTCHA_ENABLED=True)
class TestReCaptchaPermission(TestCase):
    def setUp(self) -> None:
        self.permission = ReCaptchaPermission()

    def test_missing_captcha_token_raises_validation_error(self):
        request = APIRequestFactory().post("")
        with self.assertRaises(ValidationError):
            self.permission.has_permission(request, None)

    @patch("amuse.vendor.google.captcha.is_human", return_value=False)
    def test_invalid_captcha_token_raises_validation_error(self, _):
        headers = {settings.CAPTCHA_HEADER_KEY: 'x'}
        request = APIRequestFactory().post("", **headers)
        with self.assertRaises(ValidationError):
            self.permission.has_permission(request, None)

    @patch("amuse.vendor.google.captcha.is_human", return_value=True)
    def test_validate_captcha_successfully(self, _):
        headers = {settings.CAPTCHA_HEADER_KEY: 'x'}
        request = APIRequestFactory().post("", **headers)
        try:
            self.permission.has_permission(request, None)
        except ValidationError:
            self.fail("Validator raised ValidationError unexpectedly!")

    @override_settings(GOOGLE_CAPTCHA_ENABLED=False)
    def test_captcha_disabled_does_not_raise_validation_error(self):
        request = APIRequestFactory().post("")
        try:
            self.permission.has_permission(request, None)
        except ValidationError:
            self.fail("Validator raised ValidationError unexpectedly!")
