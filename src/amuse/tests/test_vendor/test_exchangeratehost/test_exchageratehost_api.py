import datetime
from decimal import Decimal
from unittest import mock

import pytest
import responses
from waffle.testutils import override_switch

from amuse.vendor.exchangeratehost import ExchangeRateHost

SWITCH_NAME = 'service:exchangeratehost:enabled'


@responses.activate
@pytest.mark.django_db
@override_switch(SWITCH_NAME, active=True)
def test_exchangeratehost_send():
    endpoint = 'https://api.fake.url'
    responses.add(responses.GET, endpoint, status=200, json={})
    client = ExchangeRateHost()
    assert client.send(endpoint, params={'a': 123}) == {}


@responses.activate
@pytest.mark.django_db
@override_switch(SWITCH_NAME, active=False)
def test_exchangeratehost_send_inactive():
    endpoint = 'https://api.fake.url'
    responses.add(responses.GET, endpoint, status=200, json={})
    client = ExchangeRateHost()
    assert client.send(endpoint, params={'a': 123}) == None


@responses.activate
@pytest.mark.django_db
@override_switch(SWITCH_NAME, active=True)
@mock.patch("amuse.vendor.exchangeratehost.api.logger.error", autospec=True)
def test_exchangeratehost_send_fail(mock_logger):
    endpoint = 'https://api.fake.url'
    responses.add(
        responses.GET,
        endpoint,
        status=200,
        json={'success': False, 'error': 'Access Restricted'},
    )
    client = ExchangeRateHost()
    assert client.send(endpoint, params={'a': 123}) is None
    mock_logger.assert_called_once()


@responses.activate
@pytest.mark.django_db
@override_switch(SWITCH_NAME, active=True)
@mock.patch("amuse.vendor.exchangeratehost.api.logger.error", autospec=True)
def test_exchangeratehost_send_httperror(mock_logger):
    endpoint = 'https://api.fake.url'
    responses.add(responses.GET, endpoint, status=400, json={})
    client = ExchangeRateHost()
    assert client.send(endpoint, params={}) is None
    mock_logger.assert_called_once()


@responses.activate
@pytest.mark.django_db
@override_switch(SWITCH_NAME, active=True)
@mock.patch("amuse.vendor.exchangeratehost.api.logger.error", autospec=True)
@mock.patch('requests.get', side_effect=Exception())
def test_exchangeratehost_send_exception(_, mock_logger):
    endpoint = 'https://api.fake.url'
    responses.add(responses.GET, endpoint, status=200, json=2)
    client = ExchangeRateHost()
    assert client.send(endpoint, params={}) is None
    mock_logger.assert_called_once()


@responses.activate
@pytest.mark.django_db
@override_switch(SWITCH_NAME, active=True)
@mock.patch("amuse.vendor.exchangeratehost.ExchangeRateHost.send", autospec=True)
def test_exchangeratehost_live(mock_send):
    client = ExchangeRateHost()
    client.live('SEK')
    mock_send.assert_called_once_with(
        client,
        'https://api.exchangerate.host/latest',
        params={'base': 'SEK', 'places': 4},
    )


@responses.activate
@pytest.mark.django_db
@override_switch(SWITCH_NAME, active=True)
@mock.patch("amuse.vendor.exchangeratehost.ExchangeRateHost.send", autospec=True)
def test_exchangeratehost_historical(mock_send):
    today = datetime.date.today()

    client = ExchangeRateHost()
    client.historical(date=today, base_currency='SEK')
    mock_send.assert_called_once_with(
        client,
        f'https://api.exchangerate.host/{today.strftime("%Y-%m-%d")}',
        params={'base': 'SEK', 'places': 4},
    )


@pytest.mark.django_db
@override_switch(SWITCH_NAME, active=True)
@mock.patch(
    "amuse.vendor.exchangeratehost.ExchangeRateHost.send",
    return_value={'result': Decimal('23.56')},
)
def test_exchangeratehost_convert(mock_send):
    today = datetime.date.today()

    client = ExchangeRateHost()
    actual = client.convert(from_currency='EUR', to_currency='SEK', amount=12.34)
    mock_send.assert_called_once_with(
        'https://api.exchangerate.host/convert',
        params={
            'date': today.strftime("%Y-%m-%d"),
            'from': 'EUR',
            'to': 'SEK',
            'amount': 12.34,
            'places': 4,
        },
    )
    assert actual == Decimal('23.56')


@pytest.mark.django_db
@override_switch(SWITCH_NAME, active=True)
@mock.patch("amuse.vendor.exchangeratehost.ExchangeRateHost.send", return_value=None)
def test_exchangeratehost_convert_none(mock_send):
    today = datetime.date.today()

    client = ExchangeRateHost()
    actual = client.convert(from_currency='EUR', to_currency='SEK', amount=12.34)
    mock_send.assert_called_once_with(
        'https://api.exchangerate.host/convert',
        params={
            'date': today.strftime("%Y-%m-%d"),
            'from': 'EUR',
            'to': 'SEK',
            'amount': 12.34,
            'places': 4,
        },
    )
    assert actual is None
