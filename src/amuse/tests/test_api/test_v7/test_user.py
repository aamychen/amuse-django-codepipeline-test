from unittest.mock import patch

import responses
from django.urls import reverse_lazy as reverse
from rest_framework.response import Response

from amuse.services.usermanagement.user_login_service import (
    UserLoginService,
    GoogleSignInHandler,
    FacebookSignInHandler,
    AppleSignInHandler,
)
from amuse.tests.test_api.base import AmuseAPITestCase, API_V7_ACCEPT_VALUE


class GoogleLoginV7APITestCase(AmuseAPITestCase):
    @responses.activate
    def setUp(self):
        super().setUp()
        self.url = reverse('user-google')
        self.client.credentials(HTTP_ACCEPT=API_V7_ACCEPT_VALUE)

    @responses.activate
    @patch.object(GoogleSignInHandler, '__init__', return_value=None)
    @patch.object(UserLoginService, '_common', return_value=Response({}, 200))
    def test_success(self, mock_common, mock_handler_ctor):
        body = {'google_id': '1337', 'google_id_token': 'hunter2'}
        response = self.client.post(self.url, body)

        mock_handler_ctor.assert_called_once_with('1337', 'hunter2')
        mock_common.assert_called_once()
        self.assertEqual(response.status_code, 200)

    @responses.activate
    def test_invalid_request(self):
        tests = [
            {'google_id': '', 'google_id_token': 'abc'},
            {'google_id_token': 'abc'},
            {'google_id': 'abv', 'google_id_token': ''},
            {'google_id': 'abc'},
        ]
        for test in tests:
            with self.subTest():
                response = self.client.post(self.url, test)
                self.assertEqual(response.status_code, 400)


class AppleLoginV7APITestCase(AmuseAPITestCase):
    @responses.activate
    def setUp(self):
        super().setUp()
        self.url = reverse('user-apple')
        self.client.credentials(HTTP_ACCEPT=API_V7_ACCEPT_VALUE)

    @responses.activate
    @patch.object(AppleSignInHandler, '__init__', return_value=None)
    @patch.object(UserLoginService, '_common', return_value=Response({}, 200))
    def test_success(self, mock_common, mock_handler_ctor):
        body = {'access_token': '1337', 'apple_signin_id': 'hunter2'}
        response = self.client.post(self.url, body)

        mock_handler_ctor.assert_called_once_with('1337', 'hunter2')
        mock_common.assert_called_once()
        self.assertEqual(response.status_code, 200)

    @responses.activate
    def test_invalid_request(self):
        tests = [
            {'access_token': '', 'apple_signin_id': 'abc'},
            {'apple_signin_id': 'abc'},
            {'access_token': 'abc', 'apple_signin_id': ''},
            {'access_token': 'abc'},
        ]
        for test in tests:
            with self.subTest():
                response = self.client.post(self.url, test)
                self.assertEqual(response.status_code, 400)


class AppleFacebookV7APITestCase(AmuseAPITestCase):
    @responses.activate
    def setUp(self):
        super().setUp()
        self.url = reverse('user-facebook')
        self.client.credentials(HTTP_ACCEPT=API_V7_ACCEPT_VALUE)

    @responses.activate
    @patch.object(FacebookSignInHandler, '__init__', return_value=None)
    @patch.object(UserLoginService, '_common', return_value=Response({}, 200))
    def test_success(self, mock_common, mock_handler_ctor):
        body = {'facebook_id': '1337', 'facebook_access_token': 'hunter2'}
        response = self.client.post(self.url, body)

        mock_handler_ctor.assert_called_once_with('1337', 'hunter2')
        mock_common.assert_called_once()
        self.assertEqual(response.status_code, 200)

    @responses.activate
    def test_invalid_request(self):
        tests = [
            {'facebook_id': '', 'facebook_access_token': 'abc'},
            {'facebook_access_token': 'abc'},
            {'facebook_id': 'abc', 'facebook_access_token': ''},
            {'facebook_id': 'abc'},
        ]
        for test in tests:
            with self.subTest():
                response = self.client.post(self.url, test)
                self.assertEqual(response.status_code, 400)
