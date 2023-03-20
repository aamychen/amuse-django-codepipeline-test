from unittest import mock

from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from amuse.tests.test_api.base import AmuseAPITestCase, API_V2_ACCEPT_VALUE
from users.tests.factories import UserFactory


class ActivityTestCase(AmuseAPITestCase):
    def setUp(self):
        self.client.credentials(HTTP_ACCEPT=API_V2_ACCEPT_VALUE)
        # A dummy user object for signing in
        self.test_user = UserFactory.create()

    def test_endpoint(self):
        self.test_slayer_path = 'summary'
        self.slayer_request_number = 0

        def user_activity_side_effect(*args):
            self.assertEqual(args[0], int(self.test_user.id))
            self.assertEqual(args[1], self.test_slayer_path)
            self.slayer_request_number += 1
            return {'test_key': f'test_value_{self.slayer_request_number}'}

        with mock.patch('amuse.api.base.views.activity.user_activity') as mock_ua:
            mock_ua.side_effect = user_activity_side_effect

            proper_url = reverse(
                'user-activity', args=(int(self.test_user.id), self.test_slayer_path)
            )
            wrong_user_url = reverse(
                'user-activity',
                kwargs={
                    'user_id': int(self.test_user.id) + 1,
                    'path': self.test_slayer_path,
                },
            )

            client = APIClient()

            response = client.get(proper_url)
            self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

            client.force_authenticate(user=self.test_user)

            response = client.get(wrong_user_url)
            self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

            successful_response = client.get(proper_url)
            self.assertEqual(successful_response.status_code, status.HTTP_200_OK)

            # Should be retrieved from cache
            cached_response = client.get(proper_url)
            self.assertEqual(mock_ua.call_count, 1)
            self.assertEqual(cached_response.content, successful_response.content)
