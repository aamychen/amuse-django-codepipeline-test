from django.urls import reverse
from rest_framework import status

from countries.tests.factories import CountryFactory
from ..base import AmuseAPITestCase


class CountryAPITestCase(AmuseAPITestCase):
    def test_list(self):
        url = reverse('country-list')
        self.assertEqual(url, '/api/countries/')

        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 0)

        code_and_names = [
            ('DK', 'Denmark'),
            ('NO', 'Norway'),
            ('SE', 'Sweden'),
            ('US', 'United States'),
        ]
        countries = [
            CountryFactory(code=code, name=name) for code, name in code_and_names
        ]
        countries.append(
            CountryFactory(
                code='ZW',
                name='Zimbabwe',
                dial_code=None,
                is_yt_content_id_enabled=True,
            )
        )
        countries_list_size = 5
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), countries_list_size)
        for index, country in enumerate(countries):
            self.assertEqual(response.data[index]['code'], country.code)
            self.assertEqual(
                response.data[index]['is_hyperwallet_enabled'],
                country.is_hyperwallet_enabled,
            )
            self.assertEqual(response.data[index]['dial_code'], country.dial_code)
            self.assertEqual(
                response.data[index]['is_yt_content_id_enabled'],
                country.is_yt_content_id_enabled,
            )
