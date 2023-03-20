from unittest.mock import patch

import responses
from django.test import TestCase
from rest_framework.test import APIRequestFactory

from amuse.services.usermanagement.signin_handlers import FacebookSignInHandler
from users.tests.factories import UserFactory


class TestFacebookSignInHandlerCase(TestCase):
    def setUp(self):
        self.facebook_graph_url = 'https://graph.facebook.com/v8.0/me?access_token=access-token&fields=first_name,last_name'
        self.request = APIRequestFactory().request()

    @responses.activate
    @patch('amuse.tasks.zendesk_create_or_update_user')
    def test_successful_authentication(self, _):
        original_user = UserFactory(
            facebook_id='facebook-id', first_name='', last_name=''
        )

        with responses.RequestsMock() as mocked_request:
            mocked_request.add(
                responses.GET,
                self.facebook_graph_url,
                status=200,
                json={'id': 'facebook-id', 'first_name': 'Jon', 'last_name': 'Snow'},
                match_querystring=True,
            )

            handler = FacebookSignInHandler('facebook-id', 'access-token')
            user = handler.authenticate(self.request)
            self.assertIsNotNone(user)
            self.assertEqual(user.pk, original_user.pk)
            self.assertEqual(original_user.pk, user.pk)
            self.assertEqual(user.first_name, 'Jon')
            self.assertEqual(user.last_name, 'Snow')

    @responses.activate
    def test_unsuccessful_authentication(self):
        with responses.RequestsMock() as mocked_request:
            mocked_request.add(
                responses.GET,
                self.facebook_graph_url,
                status=200,
                json={'id': 'fake-id', 'first_name': 'Jon', 'last_name': 'Snow'},
                match_querystring=True,
            )

            handler = FacebookSignInHandler('facebook-id', 'access-token')
            user = handler.authenticate(self.request)
            self.assertIsNone(user)

    @responses.activate
    def test_unsuccessful_authentication_if_facebook_returns_error(self):
        with responses.RequestsMock() as mocked_request:
            mocked_request.add(
                responses.GET,
                self.facebook_graph_url,
                status=400,
                match_querystring=True,
            )

            handler = FacebookSignInHandler('facebook-id', 'access-token')
            user = handler.authenticate(self.request)
            self.assertIsNone(user)
