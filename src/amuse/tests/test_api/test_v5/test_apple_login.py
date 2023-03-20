from unittest.mock import patch

import responses
from django.urls import reverse
from rest_framework import status
from datetime import datetime

from amuse.tests.test_api.base import API_V5_ACCEPT_VALUE, AmuseAPITestCase
from users.models.user import OtpDevice
from users.tests.factories import UserFactory, UserMetadataFactory


class AppleLoginV5APITestCase(AmuseAPITestCase):
    @responses.activate
    def setUp(self):
        super().setUp()
        self.url = reverse('user-apple')
        self.client.credentials(HTTP_ACCEPT=API_V5_ACCEPT_VALUE)

    @responses.activate
    @patch("amuse.api.base.viewsets.user.apple_authenticate")
    @patch('amuse.tasks.zendesk_create_or_update_user')
    def test_apple_login_does_not_require_2fa(
        self, mock_zendesk, mock_apple_authenticate
    ):
        apple_signin_id = 'blahonga'
        UserFactory(phone_verified=True, apple_signin_id=apple_signin_id)
        data = {'access_token': '213', 'apple_signin_id': apple_signin_id}

        response = self.client.post(self.url, data)

        assert OtpDevice.objects.count() == 0
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    @responses.activate
    @patch("amuse.api.base.viewsets.user.apple_authenticate")
    @patch('amuse.tasks.zendesk_create_or_update_user')
    def test_login_fails_user_requested_delete(
        self, mock_zendesk, mock_apple_authenticate
    ):
        apple_signin_id = 'blahonga'
        user = UserFactory(phone_verified=True, apple_signin_id=apple_signin_id)
        UserMetadataFactory(
            user=user, is_delete_requested=True, delete_requested_at=datetime.now()
        )

        data = {'access_token': '213', 'apple_signin_id': apple_signin_id}

        response = self.client.post(self.url, data)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.json()['email'], 'User is deleted')
