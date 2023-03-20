from unittest.mock import patch

from django.test import TestCase
from rest_framework.test import APIRequestFactory

from amuse.services.usermanagement.signin_handlers import EmailSignInHandler
from users.tests.factories import UserFactory


class TestEmailSigninInHandlerCase(TestCase):
    @patch('amuse.tasks.zendesk_create_or_update_user')
    def setUp(self, _):
        self.user = UserFactory()
        self.request = APIRequestFactory().request()

    def test_successful_authentication(self):
        handler = EmailSignInHandler(self.user.email, UserFactory.password)
        user = handler.authenticate(self.request)
        self.assertIsNotNone(user)
        self.assertEqual(self.user.pk, user.pk)

    def test_unsuccessful_authentication(self):
        handler = EmailSignInHandler(self.user.email, "123")
        user = handler.authenticate(self.request)
        self.assertIsNone(user)
