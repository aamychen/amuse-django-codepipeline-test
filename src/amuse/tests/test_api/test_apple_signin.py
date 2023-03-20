from unittest.mock import patch

import responses
from django.urls import reverse_lazy as reverse
from rest_framework import status

from amuse.tests.test_api.base import (
    AmuseAPITestCase,
    API_V2_ACCEPT_VALUE,
    API_V5_ACCEPT_VALUE,
)
from users.tests.factories import UserFactory


class TestAppleSignInTestCase(AmuseAPITestCase):
    def setUp(self):
        self.url = reverse('user-apple')
        self.client.credentials(HTTP_ACCEPT=API_V5_ACCEPT_VALUE)

    @responses.activate
    def test_bad_request_if_access_token_missing(self):
        payload = {"access_token": "", "apple_signin_id": ""}
        response = self.client.post(self.url, payload, format='json')

        self.assertEqual(status.HTTP_400_BAD_REQUEST, response.status_code)

    @responses.activate
    def test_bad_request_if_apple_signin_missing(self):
        payload = {"access_token": "xyz", "apple_signin_id": ""}
        response = self.client.post(self.url, payload, format='json')

        self.assertEqual(status.HTTP_400_BAD_REQUEST, response.status_code)

    @responses.activate
    @patch("amuse.api.base.viewsets.user.apple_authenticate")
    def test_unauthorized_if_apple_signin_fails(self, mock_apple_authenticate):
        mock_apple_authenticate.return_value = False

        payload = {"access_token": "xyz", "apple_signin_id": "bnm"}
        response = self.client.post(self.url, payload, format='json')

        self.assertEqual(status.HTTP_401_UNAUTHORIZED, response.status_code)

    @responses.activate
    @patch("amuse.api.base.viewsets.user.apple_authenticate")
    def test_success_if_apple_signin_pass(self, mock_apple_authenticate):
        mock_apple_authenticate.return_value = True

        url = reverse('user-apple')

        payload = {"access_token": "xyz", "apple_signin_id": "bnm"}
        response = self.client.post(url, payload, format='json')

        self.assertEqual(len(response.data), 0)
        self.assertEqual(status.HTTP_200_OK, response.status_code)

    @responses.activate
    @patch("amuse.api.base.viewsets.user.apple_authenticate")
    def test_success_if_apple_signin_pass_for_existing_user(
        self, mock_apple_authenticate
    ):
        mock_apple_authenticate.return_value = True

        user = UserFactory(apple_signin_id="bnm")

        url = reverse('user-apple')

        payload = {"access_token": "xyz", "apple_signin_id": "bnm"}
        response = self.client.post(url, payload, format='json')

        self.assertEqual(status.HTTP_200_OK, response.status_code)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["id"], user.id)


class AppleLoginV2APITestCase(AmuseAPITestCase):
    @responses.activate
    def setUp(self):
        super().setUp()
        self.url = reverse('user-apple')
        self.client.credentials(HTTP_ACCEPT=API_V2_ACCEPT_VALUE)

    @responses.activate
    @patch("amuse.api.base.viewsets.user.apple_authenticate")
    def test_v2_returns_status_200(self, mock_apple_authenticate):
        mock_apple_authenticate.return_value = True

        url = reverse('user-apple')

        payload = {"access_token": "xyz", "apple_signin_id": "bnm"}
        response = self.client.post(url, payload, format='json')

        self.assertEqual(len(response.data), 0)
        self.assertEqual(status.HTTP_200_OK, response.status_code)
