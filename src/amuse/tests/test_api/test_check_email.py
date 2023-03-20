from django.urls import reverse
from rest_framework import status
import responses
from unittest.mock import patch

from amuse.tests.test_api.base import AmuseAPITestCase
from users.tests.factories import UserFactory


class TestEmailExists(AmuseAPITestCase):
    def setUp(self) -> None:
        self.check_email_url = reverse('check-email')
        self.user = UserFactory(email='test@example.com', facebook_id='facebook123')

    @responses.activate
    @patch('amuse.throttling.RestrictedEndpointThrottle.rate', new='100/min')
    def test_email_exists(self):
        payload = {'email': 'test@example.com'}

        response = self.client.post(self.check_email_url, payload, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['facebook'], True)
        self.assertEqual(response.data['google'], False)

    @responses.activate
    @patch('amuse.throttling.RestrictedEndpointThrottle.rate', new='100/min')
    def test_email_does_not_exist(self):
        payload = {'email': 'random_email@test.com'}

        response = self.client.post(self.check_email_url, payload, format='json')

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
