from decimal import Decimal

from django.test import TestCase

from countries.tests.factories import CountryFactory, CurrencyFactory


class CountryTest(TestCase):
    def test_vat_calculation(self):
        country = CountryFactory(vat_percentage=Decimal('0.25'))
        self.assertEqual(country.vat_amount(Decimal('45.0')), Decimal('9.0'))
        self.assertTrue(country.is_hyperwallet_enabled)

    def test_str_method(self):
        country = CountryFactory()
        self.assertEqual(str(country), country.name)

    def test_vat_percentage_api(self):
        country = CountryFactory(vat_percentage=Decimal('0.25'))
        self.assertEqual(country.vat_percentage_api(), 25.00)

    def test_fields(self):
        country = CountryFactory()
        self.assertIsNotNone(country.code)
        self.assertEqual(len(country.code), 2)
        self.assertIsNotNone(country.name)
        self.assertIsNotNone(country.vat_percentage)
        self.assertTrue(0 <= country.vat_percentage <= 1)
        self.assertIsNotNone(country.dial_code)
        self.assertTrue(0 <= country.dial_code <= 2000)
        self.assertTrue(country.is_yt_content_id_enabled)


class CurrencyTest(TestCase):
    def test_str_method(self):
        currency = CurrencyFactory()
        self.assertEqual(str(currency), f'{currency.code} - {currency.name}')
