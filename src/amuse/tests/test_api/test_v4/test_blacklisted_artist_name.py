from django.urls import reverse_lazy as reverse
from rest_framework import status

from amuse.tests.test_api.base import (
    API_V2_ACCEPT_VALUE,
    API_V4_ACCEPT_VALUE,
    AmuseAPITestCase,
)
from releases.models.blacklisted_artist_name import BlacklistedArtistName
from users.tests.factories import UserFactory


class ArtistV2APITestCase(AmuseAPITestCase):
    def setUp(self):
        super().setUp()
        user = UserFactory()
        self.client.credentials(HTTP_ACCEPT=API_V4_ACCEPT_VALUE)
        self.client.force_authenticate(user=user)

    def test_search_blacklisted_artist_name(self):
        url = reverse('blacklisted-artist-name-search')
        artist_name_1 = 'Tiesto'
        artist_name_2 = 'Tiësto'
        artist_name_3 = 'Ariana Grande'

        BlacklistedArtistName.objects.create(name=artist_name_1)
        BlacklistedArtistName.objects.create(name=artist_name_2)
        BlacklistedArtistName.objects.create(name=artist_name_3)

        response = self.client.get(url, {'name': artist_name_1})

        self.assertEqual(len(response.data), 2)
        self.assertEqual(response.data[0]['name'], artist_name_1)
        self.assertEqual(response.data[1]['name'], artist_name_2)

        response = self.client.get(url, {'name': artist_name_3})

        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['name'], artist_name_3)

    def test_search_blacklisted_artist_name_without_name_returns_missing_query_parmeters_error(
        self,
    ):
        url = reverse('blacklisted-artist-name-search')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        self.assertEqual(
            response.json(), {'detail': 'Name is missing from query parameters.'}
        )

    def test_search_wrong_api_version_return_400(self):
        self.client.credentials(HTTP_ACCEPT=API_V2_ACCEPT_VALUE)
        url = reverse('blacklisted-artist-name-search')

        response = self.client.get(url, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.json(), {'detail': 'API version is not supported.'})
