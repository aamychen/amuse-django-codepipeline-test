from unittest.mock import patch

import responses
from django.urls import reverse
from rest_framework import status

from amuse.utils import CLIENT_ANDROID, CLIENT_IOS, CLIENT_OTHER
from amuse.tests.test_api.base import (
    API_V5_ACCEPT_VALUE,
    API_V4_ACCEPT_VALUE,
    API_V3_ACCEPT_VALUE,
    API_V2_ACCEPT_VALUE,
    AmuseAPITestCase,
)
from users.models import AppsflyerDevice
from users.tests.factories import UserFactory, AppsflyerDeviceFactory


class TestAppsflyerDeviceAPITestCase(AmuseAPITestCase):
    @patch('amuse.tasks.zendesk_create_or_update_user')
    @responses.activate
    def setUp(self, mock_zendesk):
        super().setUp()
        self.url = reverse('appsflyer-devices')
        self.user = UserFactory()
        self.client.credentials(HTTP_ACCEPT=API_V5_ACCEPT_VALUE)
        self.client.force_authenticate(self.user)

    @responses.activate
    def test_create(self):
        data = {
            'appsflyer_id': '1',
            'idfa': 'idfa',
            'idfv': 'idfv',
            'aaid': 'aaid',
            'oaid': 'oaid',
            'imei': 'imei',
        }
        response = self.client.post(self.url, data)

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        device = AppsflyerDevice.objects.filter(appsflyer_id='1').first()
        self.assertIsNotNone(device)
        self.assertEqual('1', device.appsflyer_id)
        self.assertEqual('idfa', device.idfa)
        self.assertEqual('idfv', device.idfv)
        self.assertEqual('aaid', device.aaid)
        self.assertEqual('oaid', device.oaid)
        self.assertEqual('imei', device.imei)

    @responses.activate
    def test_update(self):
        data = {
            'appsflyer_id': '1',
            'idfa': 'idfa',
            'idfv': 'idfv',
            'aaid': 'aaid',
            'oaid': 'oaid',
            'imei': 'imei',
        }
        device = AppsflyerDeviceFactory(user=self.user, appsflyer_id='1')

        response = self.client.post(self.url, data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        device.refresh_from_db()
        self.assertIsNotNone(device)
        self.assertEqual('1', device.appsflyer_id)
        self.assertEqual('idfa', device.idfa)
        self.assertEqual('idfv', device.idfv)
        self.assertEqual('aaid', device.aaid)
        self.assertEqual('oaid', device.oaid)
        self.assertEqual('imei', device.imei)

    @patch(
        'amuse.api.v5.serializers.appsflyer_device.parse_client_version',
        return_value=(CLIENT_OTHER, 'N/A'),
    )
    @responses.activate
    def test_partial_update(self, mock_parse_client):
        data = {
            'appsflyer_id': '1',
            'idfa': 'idfa',
            'idfv': 'idfv',
            'aaid': 'aaid',
            'oaid': 'oaid',
            'imei': 'imei',
        }
        device = AppsflyerDeviceFactory(user=self.user, **data)

        response = self.client.post(self.url, {'appsflyer_id': '1'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        device.refresh_from_db()
        self.assertIsNotNone(device)
        self.assertEqual('1', device.appsflyer_id)
        self.assertEqual('idfa', device.idfa)
        self.assertEqual('idfv', device.idfv)
        self.assertEqual('aaid', device.aaid)
        self.assertEqual('oaid', device.oaid)
        self.assertEqual('imei', device.imei)

    @patch(
        'amuse.api.v5.serializers.appsflyer_device.parse_client_version',
        return_value=(CLIENT_IOS, 'N/A'),
    )
    @responses.activate
    def test_validate_ios(self, mock_parse_client):
        response = self.client.post(self.url, {'appsflyer_id': '1'})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        response = self.client.post(self.url, {'appsflyer_id': '2', 'idfv': 'idfv'})
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        response = self.client.post(self.url, {'appsflyer_id': '3', 'idfa': 'idfa'})
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    @patch(
        'amuse.api.v5.serializers.appsflyer_device.parse_client_version',
        return_value=(CLIENT_ANDROID, 'N/A'),
    )
    @responses.activate
    def test_validate_android(self, mock_parse_client):
        response = self.client.post(self.url, {'appsflyer_id': '1'})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        response = self.client.post(self.url, {'appsflyer_id': '2', 'aaid': 'aaid'})
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        response = self.client.post(self.url, {'appsflyer_id': '3', 'oaid': 'oaid'})
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        response = self.client.post(self.url, {'appsflyer_id': '4', 'imei': 'imei'})
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)


class TestAppsflyerDeviceWronApiVersionTestCase(AmuseAPITestCase):
    @patch('amuse.tasks.zendesk_create_or_update_user')
    @responses.activate
    def setUp(self, mock_zendesk):
        super().setUp()
        self.url = reverse('appsflyer-devices')
        self.user = UserFactory()
        self.client.force_authenticate(self.user)

    @responses.activate
    def test_wrong_api_version_return_400(self):
        api_versions = [API_V4_ACCEPT_VALUE, API_V3_ACCEPT_VALUE, API_V2_ACCEPT_VALUE]

        for version in api_versions:
            self.client.credentials(HTTP_ACCEPT=version)
            response = self.client.post(self.url, format='json')

            self.assertEqual(status.HTTP_400_BAD_REQUEST, response.status_code)
            self.assertEqual(
                response.json(), {'detail': 'API version is not supported.'}
            )
