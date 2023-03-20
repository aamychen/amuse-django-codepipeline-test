from unittest.mock import patch

from django.test import TestCase
from rest_framework.test import APIRequestFactory

from amuse.services.usermanagement.signin_handlers import AppleSignInHandler
from users.tests.factories import UserFactory

APPLE_AUTHENTICATE_PATH = (
    'amuse.services.usermanagement.signin_handlers.apple_handler.apple_authenticate'
)


class TestAppleSignInHandlerCase(TestCase):
    @patch('amuse.tasks.zendesk_create_or_update_user')
    def setUp(self, _):
        self.apple_signin_id = 'apple-id'
        self.access_token = 'access-token'
        self.user = UserFactory(apple_signin_id=self.apple_signin_id)
        self.request = APIRequestFactory().request()

    @patch(APPLE_AUTHENTICATE_PATH, return_value=True)
    def test_successful_authentication(self, mock_apple_authenticate):
        handler = AppleSignInHandler(self.access_token, self.apple_signin_id)
        user = handler.authenticate(self.request)
        mock_apple_authenticate.assert_called_once()
        self.assertIsNotNone(user)
        self.assertEqual(self.user.pk, user.pk)

    @patch(APPLE_AUTHENTICATE_PATH, return_value=False)
    def test_unsuccessful_authentication(self, mock_apple_authenticate):
        handler = AppleSignInHandler('wrong-access-token', 'wrong-signin-id')
        user = handler.authenticate(self.request)
        mock_apple_authenticate.assert_called_once()
        self.assertIsNone(user)
