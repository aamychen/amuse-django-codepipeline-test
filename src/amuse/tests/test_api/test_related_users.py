from amuse.tests.test_api.base import AmuseAPITestCase, API_V4_ACCEPT_VALUE
from users.tests.factories import UserFactory, Artistv2Factory, UserArtistRoleFactory
from releases.tests.factories import (
    ReleaseFactory,
    SongFactory,
    SongArtistRoleFactory,
    RoyaltySplitFactory,
)

from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient


class RelatedUsersTestCase(AmuseAPITestCase):
    def setUp(self):
        self.client.credentials(HTTP_ACCEPT=API_V4_ACCEPT_VALUE)
        self.path = reverse("related-users")

        self.test_user1 = UserFactory()
        self.test_user2 = UserFactory()
        self.test_user3 = UserFactory()
        self.test_user4 = UserFactory()

        test_release = ReleaseFactory(user=self.test_user1)
        self.test_song1 = SongFactory(release=test_release)

        self.test_artist1 = Artistv2Factory()
        SongArtistRoleFactory(song=self.test_song1, artist=self.test_artist1)

        # Users #1,2 belong to the team of artist #2
        UserArtistRoleFactory(user=self.test_user1, artist=self.test_artist1)
        UserArtistRoleFactory(user=self.test_user2, artist=self.test_artist1)

        # User #1 gives splits to #2,3
        RoyaltySplitFactory(user=self.test_user2, song=self.test_song1)
        RoyaltySplitFactory(user=self.test_user3, song=self.test_song1)

        # Assuming user #1 is trying to see her related
        self.client.force_authenticate(user=self.test_user1)

    def test_unauthorized_access_not_allowed(self):
        client = APIClient()
        response = client.get(self.path)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_response_format(self):
        response = self.client.get(self.path)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertSetEqual(
            set(response.data[0].keys()), {"id", "name", "profile_photo"}
        )

    def test_correct_users_related(self):
        response = self.client.get(self.path)

        # Only users #2,3 should be related
        self.assertEqual(len(response.data), 2)
        self.assertSetEqual(
            {user['id'] for user in response.data},
            {self.test_user2.id, self.test_user3.id},
        )
