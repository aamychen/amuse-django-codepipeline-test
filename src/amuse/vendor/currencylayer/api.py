import datetime
import decimal
import logging

import requests
from waffle import switch_is_active
from django.conf import settings
from requests.exceptions import HTTPError

logger = logging.getLogger(__name__)


class CurrencyLayer(object):
    """
    Client implementation for CurrencyLayer.

    Currencylayer provides a REST API with real-time and historical exchange rates.
    """

    BASE_URL = 'https://apilayer.net/api'
    ENDPOINT_LIVE = f'{BASE_URL}/live'
    ENDPOINT_HISTORICAL = f'{BASE_URL}/historical'
    ENDPOINT_CONVERT = f'{BASE_URL}/convert'
    BASE_CURRENCY = 'SEK'
    TIMEOUT = 5

    def __init__(self):
        self.client = requests.Session()
        self.client.params.update({'access_key': settings.CURRENCYLAYER_ACCESS_KEY})

    def live(self, base_currency=BASE_CURRENCY):
        """get the most recent exchange rate data"""
        return self.send(self.ENDPOINT_LIVE, params={'source': base_currency})

    def historical(self, date=datetime.date.today(), base_currency=BASE_CURRENCY):
        """ "get historical rates for a specific day"""
        return self.send(
            self.ENDPOINT_HISTORICAL, params={'date': date, 'source': base_currency}
        )

    def convert(self, from_currency, to_currency, amount, date=datetime.date.today()):
        """convert one currency to another"""
        result = self.send(
            self.ENDPOINT_CONVERT,
            params={
                'from': from_currency,
                'to': to_currency,
                'amount': amount,
                'date': date,
            },
        )

        if not result:
            return None

        return result.get('result')

    def send(self, url, params):
        try:
            if not switch_is_active('service:currencylayer:enabled'):
                return None

            self.client.params.update(**params)
            response = self.client.get(url, timeout=self.TIMEOUT)
            response.raise_for_status()

            result = response.json(
                parse_int=decimal.Decimal, parse_float=decimal.Decimal
            )

            if result.get('success') is False:
                logger.error(f'CurrencyLayer {url} respond with {result}')
                return None

            return result
        except HTTPError as e:
            logger.error(
                f'CurrencyLayer {url} respond with '
                f'code={e.response.status_code}, '
                f'reason={e.response.reason}, '
                f'text={e.response.text}'
            )
        except Exception as e:
            logger.error(f'CurrencyLayer unhandled exception: {e}')

        return None
