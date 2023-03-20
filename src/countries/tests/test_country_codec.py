from functools import reduce

from django.test import TestCase

from .factories import CountryFactory
from ..country_codec import CountryCodec


class TestCountryCodec(TestCase):
    def setUp(self):
        self.countries = [CountryFactory() for i in range(0, 10)]

    def test_encode(self):
        random_input_countries = [
            self.countries[3],
            self.countries[4],
            self.countries[8],
        ]

        expected = reduce(
            lambda x, y: x + 2**y.internal_numeric_code, random_input_countries, 0
        )

        result = CountryCodec.encode(random_input_countries)
        self.assertEqual(expected, result)

    def test_encode_none(self):
        expected = 0
        result = CountryCodec.encode(None)
        self.assertEqual(expected, result)

        result = CountryCodec.encode([])
        self.assertEqual(expected, result)

    def test_encode_single_country(self):
        expected = 2 ** self.countries[2].internal_numeric_code
        result = CountryCodec.encode(self.countries[2])
        self.assertEqual(expected, result)

    def test_decode(self):
        random_input_countries = [
            self.countries[3],
            self.countries[4],
            self.countries[8],
        ]
        code = CountryCodec.encode(random_input_countries)

        countries = CountryCodec.decode(code)

        self.assertEqual(len(random_input_countries), len(countries))
        for c in random_input_countries:
            self.assertTrue(c in countries)
