from datetime import datetime

import responses
from django.urls import reverse_lazy as reverse
from rest_framework import status

from amuse.tests.test_api.base import AmuseAPITestCase, API_V5_ACCEPT_VALUE
from users.tests.factories import UserFactory, UserMetadataFactory


class FacebookLoginAPIV5TestCase(AmuseAPITestCase):
    def setUp(self):
        super().setUp()
        self.client.credentials(HTTP_ACCEPT=API_V5_ACCEPT_VALUE)

    @classmethod
    def setUpTestData(cls):
        cls.url = reverse('user-facebook')
        cls.params = {'facebook_id': '1337', 'facebook_access_token': 'hunter2'}
        cls.facebook_graph_url = 'https://graph.facebook.com/v8.0/me'

    def test_url(self):
        self.assertEqual(self.url, '/api/users/facebook/')

    def test_default_response(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 0)

    def test_failed_response(self):
        with responses.RequestsMock() as mocked_request:
            mocked_request.add(responses.GET, self.facebook_graph_url, status=500)
            response = self.client.get(self.url, self.params)
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            self.assertEqual(len(response.data), 0)

    def test_id_mismatch(self):
        with responses.RequestsMock() as mocked_request:
            # Let's pretend the ids mismatched.
            mocked_request.add(
                responses.GET,
                f'{self.facebook_graph_url}?access_token=hunter2&fields=first_name,last_name',
                status=200,
                json={'id': '7331', 'first_name': 'Jon', 'last_name': 'Snow'},
                match_querystring=True,
            )
            response = self.client.get(self.url, self.params)
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            self.assertEqual(len(response.data), 0)

    def test_id_verified(self):
        with responses.RequestsMock() as mocked_request:
            mocked_request.add(
                responses.GET,
                f'{self.facebook_graph_url}?access_token=hunter2&fields=first_name,last_name',
                status=200,
                json={'id': '1337', 'first_name': 'Jon', 'last_name': 'Snow'},
                match_querystring=True,
            )
            response = self.client.get(self.url, self.params)
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            self.assertEqual(len(response.data), 0)

    def test_login_success(self):
        user = UserFactory(facebook_id='1337', first_name='', last_name='')

        with responses.RequestsMock() as mocked_request:
            mocked_request.add(
                responses.GET,
                f'{self.facebook_graph_url}?access_token=hunter2&fields=first_name,last_name',
                status=200,
                json={'id': '1337', 'first_name': 'Jon', 'last_name': 'Snow'},
                match_querystring=True,
            )

            response = self.client.get(self.url, self.params)
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            self.assertEqual(len(response.data), 1)

            user.refresh_from_db()
            self.assertEqual(user.first_name, 'Jon')
            self.assertEqual(user.last_name, 'Snow')

    def test_login_fails_for_inactive_user(self):
        user = UserFactory(
            facebook_id='1337', first_name='', last_name='', is_active=False
        )

        with responses.RequestsMock() as mocked_request:
            mocked_request.add(
                responses.GET,
                f'{self.facebook_graph_url}?access_token=hunter2&fields=first_name,last_name',
                status=200,
                json={'id': '1337', 'first_name': 'Jon', 'last_name': 'Snow'},
                match_querystring=True,
            )

            response = self.client.get(self.url, self.params)
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            self.assertEqual(len(response.data), 0)

            user.refresh_from_db()
            self.assertEqual(user.first_name, '')
            self.assertEqual(user.last_name, '')

    def test_login_fails_user_requested_delete(self):
        url = reverse('user-facebook')

        user = UserFactory(facebook_id='1337', first_name='', last_name='')
        UserMetadataFactory(
            user=user, is_delete_requested=True, delete_requested_at=datetime.now()
        )

        with responses.RequestsMock() as mocked_request:
            mocked_request.add(
                responses.GET,
                f'{self.facebook_graph_url}?access_token=hunter2&fields=first_name,last_name',
                status=200,
                json={'id': '1337', 'first_name': 'Jon', 'last_name': 'Snow'},
                match_querystring=True,
            )

            response = self.client.get(self.url, self.params)
            self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
            self.assertEqual(response.json()['email'], 'User is deleted')
