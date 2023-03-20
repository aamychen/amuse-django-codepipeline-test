import responses
from django.test import TestCase, override_settings
from django.contrib.auth.hashers import is_password_usable
from users.tests.factories import UserFactory
from users.models import User

from django.core.management import call_command

from amuse.tests.helpers import (
    add_zendesk_mock_post_response,
    ZENDESK_MOCK_API_URL_TOKEN,
)


@override_settings(**ZENDESK_MOCK_API_URL_TOKEN)
class SetUnusablePassCommandTestCase(TestCase):
    @responses.activate
    def setUp(self):
        add_zendesk_mock_post_response()
        self.user_null_pass = UserFactory(password=None)
        self.user_empty_string = UserFactory(password='')

    def test_command(self):
        user_null_pass_token = self.user_null_pass.auth_token.key
        user_empty_string_token = self.user_empty_string.auth_token.key
        call_command('setunusableemptypassw')
        updated_user_null_pass = User.objects.get(id=self.user_null_pass.id)
        updated_user_empty_string_pass = User.objects.get(id=self.user_empty_string.id)

        # Assert passwords are set to unusable
        assert is_password_usable(updated_user_null_pass.password) == False
        assert is_password_usable(updated_user_empty_string_pass.password) == False

        # Assert auth_token is not rotated

        assert user_empty_string_token == updated_user_empty_string_pass.auth_token.key
        assert user_null_pass_token == updated_user_null_pass.auth_token.key
