from django.test import TestCase
from rest_framework.exceptions import ValidationError
from rest_framework.test import APIRequestFactory

from amuse.api.base.validators import (
    validate_allow_max_one_field_with_value,
    validate_social_login_request_version,
)
from amuse.api.base.views.exceptions import WrongAPIversionError


class ValidateMaxOnlyOneFieldWithVale(TestCase):
    def test_raise_validation_error(self):
        tests = [
            {'obj': {'a': 1, 'b': 2, 'c': 3}, 'fields': ['a', 'b', 'c']},
            {'obj': {'a': 1, 'b': 2, 'c': 3}, 'fields': ['a', 'c']},
            {'obj': {'a': 1, 'b': 2, 'c': 3}, 'fields': ['a', 'b']},
            {'obj': {'a': 1, 'b': 2, 'c': 3}, 'fields': ['b', 'c']},
        ]

        for test in tests:
            with self.subTest():
                with self.assertRaises(ValidationError):
                    validate_allow_max_one_field_with_value(test['obj'], test['fields'])

    def test_does_not_raise_validation_error(self):
        tests = [
            {'obj': {'a': 1, 'b': 2, 'c': 3}, 'fields': []},
            {'obj': {'a': 1, 'b': 2, 'c': 3}, 'fields': ['a']},
            {'obj': {'a': 1, 'b': 2, 'c': 3}, 'fields': ['b']},
            {'obj': {'a': 1, 'b': 2, 'c': 3}, 'fields': ['c']},
            {'obj': {'a': 1, 'b': 2, 'c': 3}, 'fields': ['d']},
        ]

        for test in tests:
            with self.subTest():
                try:
                    validate_allow_max_one_field_with_value(test['obj'], test['fields'])
                except ValidationError:
                    self.fail("Validator raised ValidationError unexpectedly!")


class ValidateSocialLoginRequestVersion(TestCase):
    def setUp(self):
        self.request = APIRequestFactory().request()

    def test_raise_exception_if_invalid_version(self):
        tests = [None, '-', '', '1', '3', '4', '8', '9', '10']

        for version in tests:
            with self.subTest(), self.assertRaises(WrongAPIversionError):
                self.request.version = version
                validate_social_login_request_version(self.request)

    def test_do_not_raise_exception_for_allowed_versions(self):
        tests = ['2', '5', '6', '7']
        for version in tests:
            try:
                self.request.version = version
                validate_social_login_request_version(self.request)
            except WrongAPIversionError:
                self.fail("Validator raised WrongAPIVersionError unexpectedly!")
