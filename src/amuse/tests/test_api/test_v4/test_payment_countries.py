from unittest.mock import patch, Mock

from django.urls import reverse
from geoip2.errors import AddressNotFoundError
from rest_framework import status

from amuse.tests.test_api.base import (
    API_V2_ACCEPT_VALUE,
    API_V4_ACCEPT_VALUE,
    AmuseAPITestCase,
)
from countries.tests.factories import CountryFactory
from users.tests.factories import UserFactory


class PaymentCountriesTest(AmuseAPITestCase):
    def setUp(self):
        self.country = CountryFactory(
            is_adyen_enabled=True, vat_percentage=0.25, name='a'
        )
        CountryFactory(is_adyen_enabled=True, vat_percentage=0.25, name='b')
        self.url = reverse('payment-countries')
        self.user = UserFactory()
        self.client.credentials(HTTP_ACCEPT=API_V4_ACCEPT_VALUE)
        self.client.force_authenticate(self.user)

    def test_wrong_api_version_return_400(self):
        self.client.credentials(HTTP_ACCEPT=API_V2_ACCEPT_VALUE)

        response = self.client.post(self.url, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.json(), {'detail': 'API version is not supported.'})

    def test_permissions(self):
        self.client.logout()
        self.assertEqual(
            self.client.get(self.url).status_code, status.HTTP_401_UNAUTHORIZED
        )

    def test_returns_selectable_countries_and_detected_country(self):
        CountryFactory(is_adyen_enabled=True, name='swe', code='SE')
        expected_country_code = 'SE'

        response = self.client.get(self.url, HTTP_CF_IPCOUNTRY=expected_country_code)

        payload = response.json()
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(payload['detected_country'], expected_country_code)
        self.assertEqual(len(payload['available_countries']), 3)
        country_payload = payload['available_countries'][0]
        self.assertEqual(country_payload['code'], self.country.code)
        self.assertEqual(country_payload['vat_percentage'], "25.00")

    def test_detected_country_defaults_to_first_country_if_not_available(self):
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json()['detected_country'], self.country.code)

    def test_detected_country_defaults_to_first_country_if_not_adyen_enabled(self):
        response = self.client.get(self.url, HTTP_CF_IPCOUNTRY='NOPE')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json()['detected_country'], self.country.code)
