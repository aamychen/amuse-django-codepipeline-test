import datetime
import decimal
import logging

import requests
from requests.exceptions import HTTPError
from waffle import switch_is_active

logger = logging.getLogger(__name__)


def format_date(date):
    return date.strftime("%Y-%m-%d")


class ExchangeRateHost(object):
    """
    REST API client implementation for https://exchangerate.host/
    """

    BASE_URL = 'https://api.exchangerate.host'
    ENDPOINT_LIVE = f'{BASE_URL}/latest'
    ENDPOINT_CONVERT = f'{BASE_URL}/convert'
    BASE_CURRENCY = 'SEK'

    TIMEOUT_SEC = 2
    DECIMAL_PLACES = 4

    def __init__(self):
        self.client = requests.Session()

    def live(self, base_currency=BASE_CURRENCY):
        """
        Get the latest foreign exchange reference rates.
        Latest endpoint will return exchange rate data updated on daily basis.
        """
        return self.send(
            self.ENDPOINT_LIVE,
            params={'base': base_currency, 'places': self.DECIMAL_PLACES},
        )

    def historical(self, date, base_currency=BASE_CURRENCY):
        """
        Historical rates are available for most currencies all the way back to the year of 1999.
        You can query the API for historical rates by appending a date (format YYYY-MM-DD) to the base URL.
        """
        endpoint = f'{self.BASE_URL}/{format_date(date)}'
        return self.send(
            endpoint, params={'base': base_currency, 'places': self.DECIMAL_PLACES}
        )

    def convert(self, from_currency, to_currency, amount, date=datetime.date.today()):
        """
        Currency conversion endpoint, can be used to convert any amount from one currency to another.
        """
        result = self.send(
            self.ENDPOINT_CONVERT,
            params={
                'from': from_currency,
                'to': to_currency,
                'amount': amount,
                'date': format_date(date),
                'places': self.DECIMAL_PLACES,
            },
        )

        if result is None:
            return None

        return result.get('result', None)

    def send(self, url, params):
        try:
            if not switch_is_active('service:exchangeratehost:enabled'):
                return None

            response = self.client.get(url, params=params, timeout=self.TIMEOUT_SEC)
            response.raise_for_status()

            result = response.json(
                parse_int=decimal.Decimal, parse_float=decimal.Decimal
            )

            if result.get('success') is False:
                logger.error(f'ExchangeRateHost {url} respond with {result}')
                return None

            return result
        except HTTPError as e:
            logger.error(
                f'ExchangeRateHost {url} respond with '
                f'code={e.response.status_code}, '
                f'reason={e.response.reason}, '
                f'text={e.response.text}'
            )
        except Exception as e:
            logger.error(f'ExchangeRateHost unhandled exception: {e}')

        return None
