import datetime
from decimal import Decimal
from unittest import mock

import pytest
import responses
from django.test import override_settings
from waffle.testutils import override_switch

from amuse.vendor.currencylayer import CurrencyLayer

CURRENCYLAYER_SETTINGS = {"CURRENCYLAYER_ACCESS_KEY": "fake-currencylayer-access-key"}

SWITCH_NAME = 'service:currencylayer:enabled'


@responses.activate
@pytest.mark.django_db
@override_settings(**CURRENCYLAYER_SETTINGS)
@override_switch(SWITCH_NAME, active=False)
def test_currencylayer_send_disabled():
    endpoint = 'https://api.fake.url'
    responses.add(responses.GET, endpoint, status=200, json={})
    client = CurrencyLayer()
    assert client.send(endpoint, params={'a': 123}) == None


@responses.activate
@pytest.mark.django_db
@override_switch(SWITCH_NAME, active=True)
def test_currencylayer_send():
    endpoint = 'https://api.fake.url'
    responses.add(responses.GET, endpoint, status=200, json={})
    client = CurrencyLayer()
    assert client.send(endpoint, params={'a': 123}) == {}


@responses.activate
@pytest.mark.django_db
@override_settings(**CURRENCYLAYER_SETTINGS)
@override_switch(SWITCH_NAME, active=True)
@mock.patch("amuse.vendor.currencylayer.api.logger.error", autospec=True)
def test_currencylayer_send_fail(mock_logger):
    endpoint = 'https://api.fake.url'
    responses.add(
        responses.GET,
        endpoint,
        status=200,
        json={'success': False, 'error': 'Access Restricted'},
    )
    client = CurrencyLayer()
    assert client.send(endpoint, params={'a': 123}) is None
    mock_logger.assert_called_once()


@responses.activate
@pytest.mark.django_db
@override_settings(**CURRENCYLAYER_SETTINGS)
@override_switch(SWITCH_NAME, active=True)
@mock.patch("amuse.vendor.currencylayer.api.logger.error", autospec=True)
def test_currencylayer_send_httperror(mock_logger):
    endpoint = 'https://api.fake.url'
    responses.add(responses.GET, endpoint, status=400, json={})
    client = CurrencyLayer()
    assert client.send(endpoint, params={}) is None
    mock_logger.assert_called_once()


@responses.activate
@pytest.mark.django_db
@override_settings(**CURRENCYLAYER_SETTINGS)
@override_switch(SWITCH_NAME, active=True)
@mock.patch("amuse.vendor.currencylayer.api.logger.error", autospec=True)
@mock.patch('requests.get', side_effect=Exception())
def test_currencylayer_send_exception(_, mock_logger):
    endpoint = 'https://api.fake.url'
    responses.add(responses.GET, endpoint, status=200, json=2)
    client = CurrencyLayer()
    assert client.send(endpoint, params={}) is None
    mock_logger.assert_called_once()


@responses.activate
@pytest.mark.django_db
@override_settings(**CURRENCYLAYER_SETTINGS)
@override_switch(SWITCH_NAME, active=True)
@mock.patch("amuse.vendor.currencylayer.CurrencyLayer.send", autospec=True)
def test_currencylayer_live(mock_send):
    client = CurrencyLayer()
    client.live('SEK')
    mock_send.assert_called_once_with(
        client, 'https://apilayer.net/api/live', params={'source': 'SEK'}
    )


@responses.activate
@pytest.mark.django_db
@override_settings(**CURRENCYLAYER_SETTINGS)
@override_switch(SWITCH_NAME, active=True)
@mock.patch("amuse.vendor.currencylayer.CurrencyLayer.send", autospec=True)
def test_currencylayer_historical(mock_send):
    today = datetime.date.today()

    client = CurrencyLayer()
    client.historical(date=today, base_currency='SEK')
    mock_send.assert_called_once_with(
        client,
        'https://apilayer.net/api/historical',
        params={'date': today, 'source': 'SEK'},
    )


@responses.activate
@pytest.mark.django_db
@override_settings(**CURRENCYLAYER_SETTINGS)
@override_switch(SWITCH_NAME, active=True)
@mock.patch(
    "amuse.vendor.currencylayer.CurrencyLayer.send",
    return_value={'success': True, 'result': Decimal('12.456')},
)
def test_currencylayer_convert(mock_send):
    today = datetime.date.today()

    client = CurrencyLayer()
    actual = client.convert(from_currency='EUR', to_currency='SEK', amount=12.34)
    assert actual == Decimal('12.456')
    mock_send.assert_called_once_with(
        'https://apilayer.net/api/convert',
        params={'date': today, 'from': 'EUR', 'to': 'SEK', 'amount': 12.34},
    )


@responses.activate
@pytest.mark.django_db
@override_settings(**CURRENCYLAYER_SETTINGS)
@override_switch(SWITCH_NAME, active=True)
@mock.patch("amuse.vendor.currencylayer.CurrencyLayer.send", return_value=None)
def test_currencylayer_convert_fail(mock_send):
    today = datetime.date.today()

    client = CurrencyLayer()
    actual = client.convert(from_currency='EUR', to_currency='SEK', amount=12.34)
    assert actual is None
    mock_send.assert_called_once_with(
        'https://apilayer.net/api/convert',
        params={'date': today, 'from': 'EUR', 'to': 'SEK', 'amount': 12.34},
    )
