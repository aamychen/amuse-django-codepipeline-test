from django.db.utils import OperationalError
from releases.tests.factories import GenreFactory
from rest_framework import status
from rest_framework.test import APITestCase
from unittest import mock


class HealthCheckTestCase(APITestCase):
    databases = {'default', 'replica'}

    def test_healthcheck_tries_to_access_db(self):
        with mock.patch('amuse.health.Genre') as GenreMock:
            response = self.client.get('/health/')
            GenreMock.objects.first.assert_called()

    def test_healthcheck_succeeds(self):
        response = self.client.get('/health/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
