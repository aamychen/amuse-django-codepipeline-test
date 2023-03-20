from decimal import Decimal
from unittest import mock

import pytest

from amuse.vendor.adyen.vat import calculate_vat
from amuse.vendor.currencylayer import CurrencyLayer
from amuse.vendor.exchangeratehost import ExchangeRateHost
from countries.tests.factories import CountryFactory


@pytest.mark.django_db
@mock.patch.object(ExchangeRateHost, 'convert')
@mock.patch.object(CurrencyLayer, 'convert')
def test_calulate_vat_currency_sek(mock_currency_layer, mock_exchangerate_host):
    country = CountryFactory(vat_percentage=Decimal('0.1'))

    vat_amount, vat_amount_sek = calculate_vat(country, 'SEK', Decimal('10.00'))
    assert vat_amount == Decimal('0.91')
    assert vat_amount_sek == vat_amount

    assert mock_currency_layer.call_count == 0
    assert mock_exchangerate_host.call_count == 0


@pytest.mark.django_db
@mock.patch.object(ExchangeRateHost, 'convert')
@mock.patch.object(CurrencyLayer, 'convert')
def test_calulate_vat_0(mock_currency_layer, mock_exchangerate_host):
    country = CountryFactory(vat_percentage=Decimal('0.0'))

    vat_amount, vat_amount_sek = calculate_vat(country, 'XYZ', Decimal('10.00'))
    assert vat_amount == Decimal('0.0')
    assert vat_amount_sek == vat_amount

    assert mock_currency_layer.call_count == 0
    assert mock_exchangerate_host.call_count == 0


@pytest.mark.django_db
@mock.patch.object(ExchangeRateHost, 'convert')
@mock.patch.object(CurrencyLayer, 'convert', return_value=Decimal('1.234'))
def test_calulate_vat_currencylayer(mock_currency_layer, mock_exchangerate_host):
    country = CountryFactory(vat_percentage=Decimal('0.1'))

    vat_amount, vat_amount_sek = calculate_vat(country, 'XYZ', Decimal('10.00'))
    assert vat_amount == Decimal('0.91')
    assert vat_amount_sek == Decimal('1.23')

    assert mock_currency_layer.call_count == 1
    assert mock_exchangerate_host.call_count == 0


@pytest.mark.django_db
@mock.patch.object(ExchangeRateHost, 'convert', return_value=Decimal('1.234'))
@mock.patch.object(CurrencyLayer, 'convert', return_value=None)
def test_calulate_vat_exchange_rate(mock_currency_layer, mock_exchangerate_host):
    country = CountryFactory(vat_percentage=Decimal('0.1'))

    vat_amount, vat_amount_sek = calculate_vat(country, 'XYZ', Decimal('10.00'))
    assert vat_amount == Decimal('0.91')
    assert vat_amount_sek == Decimal('1.23')

    assert mock_currency_layer.call_count == 1
    assert mock_exchangerate_host.call_count == 1


@pytest.mark.django_db
@mock.patch.object(ExchangeRateHost, 'convert', return_value=None)
@mock.patch.object(CurrencyLayer, 'convert', return_value=None)
def test_calulate_vat_exchange_none(mock_currency_layer, mock_exchangerate_host):
    country = CountryFactory(vat_percentage=Decimal('0.1'))

    vat_amount, vat_amount_sek = calculate_vat(country, 'XYZ', Decimal('10.00'))
    assert vat_amount == Decimal('0.91')
    assert vat_amount_sek == None

    assert mock_currency_layer.call_count == 1
    assert mock_exchangerate_host.call_count == 1
