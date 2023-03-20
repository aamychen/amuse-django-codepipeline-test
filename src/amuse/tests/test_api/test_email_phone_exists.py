import responses
from rest_framework import status
from django.urls import reverse_lazy as reverse
from users.tests.factories import UserFactory
from .base import AmuseAPITestCase
from unittest.mock import patch


class ReleaseAPITestCase(AmuseAPITestCase):
    def setUp(self):
        super(ReleaseAPITestCase, self).setUp()

        self.user = UserFactory(
            artist_name='Big Cat', email='test@example.com', phone='+541138196307'
        )

    @responses.activate
    @patch('amuse.throttling.RestrictedEndpointThrottle.rate', new='100/min')
    def test_email_exists(self):
        url = reverse('email-exists')
        payload = {'email': "test@example.com"}
        response = self.client.post(url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['exists'], True)

    @responses.activate
    @patch('amuse.throttling.RestrictedEndpointThrottle.rate', new='100/min')
    def test_email_not_exists(self):
        url = reverse('email-exists')
        payload = {'email': 'notexist@example.com'}
        response = self.client.post(url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['exists'], False)

    @responses.activate
    @patch('amuse.throttling.RestrictedEndpointThrottle.rate', new='100/min')
    def test_phone_exists(self):
        url = reverse('phone-exists')
        payload = {'phone_number': '+541138196307'}
        response = self.client.post(url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['exists'], True)

    @responses.activate
    @patch('amuse.throttling.RestrictedEndpointThrottle.rate', new='100/min')
    def test_phone_not_exists(self):
        url = reverse('phone-exists')
        payload = {'phone_number': '+541138196308'}
        response = self.client.post(url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['exists'], False)

    @responses.activate
    @patch('amuse.throttling.RestrictedEndpointThrottle.rate', new='100/min')
    def test_email_validator(self):
        url = reverse('email-exists')
        payload = {'email': 'wrongemailformat'}
        response = self.client.post(url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data['message'], "Invalid email.")

    @responses.activate
    @patch('amuse.throttling.RestrictedEndpointThrottle.rate', new='100/min')
    def test_phone_validator(self):
        url = reverse('phone-exists')
        payload = {'phone_number': '0000'}
        response = self.client.post(url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data['message'], "Invalid phone number.")
