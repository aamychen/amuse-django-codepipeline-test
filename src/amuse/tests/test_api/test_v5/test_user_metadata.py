from unittest import mock

import responses
from django.urls import reverse
from rest_framework import status

from amuse.tests.test_api.base import (
    API_V4_ACCEPT_VALUE,
    API_V5_ACCEPT_VALUE,
    AmuseAPITestCase,
)
from users.models.user import UserMetadata
from users.tests.factories import UserFactory


class UserMetadataTestCase(AmuseAPITestCase):
    @mock.patch('amuse.tasks.zendesk_create_or_update_user')
    def setUp(self, mocked_zendesk):
        self.user = UserFactory(phone_verified=True, otp_enabled=True)
        self.client.force_authenticate(self.user)
        self.client.credentials(HTTP_ACCEPT=API_V5_ACCEPT_VALUE)
        self.url = reverse('user-metadata')

    @mock.patch('amuse.api.base.views.user_metadata.sign_up')
    def test_update_user_metadata(self, mock_analytics):
        def run_test(click_id):
            response = self.client.put(self.url, {'impact_click_id': click_id})

            self.assertEqual(response.status_code, status.HTTP_200_OK)
            self.assertEqual(response.json()['is_success'], True)
            self.assertEqual(1, UserMetadata.objects.filter(user=self.user).count())
            self.assertEqual(
                click_id,
                UserMetadata.objects.filter(user=self.user).first().impact_click_id,
            )
            mock_analytics.assert_called_once_with(self.user, 0, click_id)
            mock_analytics.reset_mock()

        run_test('click_id_1')
        run_test('click_id_2')

    @responses.activate
    def test_bad_request_for_invalid_api_version(self):
        self.client.credentials(HTTP_ACCEPT=API_V4_ACCEPT_VALUE)

        response = self.client.put(self.url, {'impact_click_id': 'click_123_abc'})

        self.assertEqual(status.HTTP_400_BAD_REQUEST, response.status_code)
        self.assertIn('detail', response.data)
        self.assertEqual(response.json(), {'detail': 'API version is not supported.'})
