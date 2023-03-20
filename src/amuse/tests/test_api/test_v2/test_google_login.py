import responses

from django.urls import reverse_lazy as reverse
from rest_framework import status
from datetime import datetime

from amuse.tests.test_api.base import AmuseAPITestCase, API_V2_ACCEPT_VALUE
from users.tests.factories import UserFactory, UserMetadataFactory


class GoogleLoginV2APITestCase(AmuseAPITestCase):
    @responses.activate
    def setUp(self):
        super().setUp()
        self.url = reverse('user-google')
        self.client.credentials(HTTP_ACCEPT=API_V2_ACCEPT_VALUE)

    def test_v2_returns_status_200(self):
        params = {'google_id': '1337', 'google_id_token': 'hunter2'}

        with responses.RequestsMock() as response:
            response.add(
                responses.GET,
                ('https://www.googleapis.com/oauth2/v3/tokeninfo?' 'id_token=hunter2'),
                status=200,
                match_querystring=True,
                json={},
            )
            response = self.client.get(self.url, params)
            self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_login_fails_user_requested_delete(self):
        params = {'google_id': '1337', 'google_id_token': 'hunter2'}

        self.user = UserFactory(google_id=1337)
        UserMetadataFactory(
            user=self.user, is_delete_requested=True, delete_requested_at=datetime.now()
        )

        with responses.RequestsMock() as response:
            response.add(
                responses.GET,
                ('https://www.googleapis.com/oauth2/v3/tokeninfo?' 'id_token=hunter2'),
                status=200,
                match_querystring=True,
                json={'sub': '1337'},
            )
            response = self.client.get(self.url, params)
            self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
            self.assertEqual(response.json()['email'], 'User is deleted')
