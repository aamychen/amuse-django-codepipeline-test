from django.urls import reverse_lazy as reverse
import responses
from rest_framework import status

from amuse.tests.test_api.base import (
    API_V2_ACCEPT_VALUE,
    API_V4_ACCEPT_VALUE,
    AmuseAPITestCase,
)
from users.tests.factories import UserFactory


class ArtistV2APITestCase(AmuseAPITestCase):
    def setUp(self):
        self.user = UserFactory()
        self.client.credentials(HTTP_ACCEPT=API_V4_ACCEPT_VALUE)
        self.client.force_authenticate(user=self.user)
        self.payload = {
            "name": "Test Artist v2",
            "spotify_id": "7dGJo4pcD2V6oG8kP0tJRR",
        }
        self.url = reverse('create-contributor-artist')

    def test_create_contributor_artist(self):
        expected_response_keys = ['id', 'name', 'spotify_id', 'has_owner']

        response = self.client.post(self.url, self.payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(list(response.data.keys()), expected_response_keys)

        self.assertIsNotNone(response.data['id'])
        self.assertEqual(self.payload['name'], response.data['name'])
        self.assertEqual(self.payload['spotify_id'], response.data['spotify_id'])
        self.assertFalse(response.data['has_owner'])

    def test_create_contributor_artist_with_unsupported_api_version_returns_error(self):
        self.client.credentials(HTTP_ACCEPT=API_V2_ACCEPT_VALUE)
        response = self.client.post(self.url, self.payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.json(), {'detail': 'API version is not supported.'})
