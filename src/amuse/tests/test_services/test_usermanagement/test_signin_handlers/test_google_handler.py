from unittest.mock import patch

import responses
from django.test import TestCase
from rest_framework.test import APIRequestFactory

from amuse.services.usermanagement.signin_handlers import GoogleSignInHandler
from users.tests.factories import UserFactory


class TestGoogleSignInHandlerCase(TestCase):
    def setUp(self):
        self.google_id = 'google-id'
        self.google_id_token = 'google-id-token'
        self.request = APIRequestFactory().request()

    @responses.activate
    @patch('amuse.tasks.zendesk_create_or_update_user')
    def test_successful_authentication(self, _):
        original_user = UserFactory(
            google_id=self.google_id, first_name='', last_name=''
        )

        url = f'https://www.googleapis.com/oauth2/v3/tokeninfo?id_token={self.google_id_token}'
        with responses.RequestsMock() as mock:
            mock.add(
                responses.GET,
                url=url,
                status=200,
                json={'sub': self.google_id, 'given_name': 'A', 'family_name': 'B'},
            )

            handler = GoogleSignInHandler(self.google_id, self.google_id_token)
            user = handler.authenticate(self.request)
            self.assertIsNotNone(user)
            self.assertEqual(original_user.pk, user.pk)
            self.assertEqual(user.first_name, 'A')
            self.assertEqual(user.last_name, 'B')

    @responses.activate
    def test_unsuccessful_authentication(
        self,
    ):
        url = f'https://www.googleapis.com/oauth2/v3/tokeninfo?id_token=wrong-google-id-token'
        with responses.RequestsMock() as mock:
            mock.add(responses.GET, url=url, status=200, json={'sub': self.google_id})
            handler = GoogleSignInHandler('wrong-google-id', 'wrong-google-id-token')
            user = handler.authenticate(self.request)
            self.assertIsNone(user)

    @responses.activate
    def test_unsuccessful_authentication_if_google_return_400(self):
        url = f'https://www.googleapis.com/oauth2/v3/tokeninfo?id_token=wrong-google-id-token'
        with responses.RequestsMock() as mock:
            mock.add(responses.GET, url=url, status=400, json={})
            handler = GoogleSignInHandler('wrong-google-id', 'wrong-google-id-token')
            user = handler.authenticate(self.request)
            self.assertIsNone(user)
