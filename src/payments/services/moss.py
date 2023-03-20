import csv
import math
from datetime import datetime, timezone, timedelta
from decimal import Decimal

from countries.models import ExchangeRate, Country
from payments.models import PaymentTransaction
from subscriptions.models import Subscription

MOSS_COUNTRY_CODES = (
    'AT',
    'BE',
    'BG',
    'CY',
    'CZ',
    'DE',
    'DK',
    'EE',
    'ES',
    'FI',
    'FR',
    'GR',
    'HR',
    'HU',
    'IE',
    'IT',
    'LT',
    'LU',
    'LV',
    'MT',
    'NL',
    'PL',
    'PT',
    'RO',
    'SI',
    'SK',
)
MOSS_COUNTRY_LABELS = {'GR': 'EL'}
CSV_HEADER_TITLE = 'MOSS_001'
CSV_HEADER_ID = 'SE559036701601'


class MossReportException(Exception):
    pass


class MossReport(object):
    def __init__(self, year, month, quarter=None, country=None):
        self.year, self.quarter, self.month = self._get_financial_period(
            year=year, quarter=quarter, month=month
        )
        self.countries = [country] if country else MOSS_COUNTRY_CODES

    def generate_report(self, fileobj):
        period_start, period_end = self._get_period()
        transactions = PaymentTransaction.objects.filter(
            country__in=self.countries,
            created__gte=period_start,
            created__lt=period_end,
            status=PaymentTransaction.STATUS_APPROVED,
            subscription__provider=Subscription.PROVIDER_ADYEN,
            type=PaymentTransaction.TYPE_PAYMENT,
        ).select_related('currency')

        vat_per_country = self._get_vatless_amount_per_country(
            self.countries, transactions
        )
        self._print_moss_file(vat_per_country, fileobj)

    def _get_financial_period(self, year, quarter, month=None):
        today = datetime.utcnow()
        if year is None:
            year = today.year

        if month is not None:
            # we ignore the quarter argument and set quarter for month
            if month in [1, 2, 3]:
                quarter = 1
            elif month in [4, 5, 6]:
                quarter = 2
            elif month in [7, 8, 9]:
                quarter = 3
            elif month in [10, 11, 12]:
                quarter = 4
            else:
                raise MossReportException(f'Invalid month number entered: {month}')

        elif quarter is None:
            quarter = math.floor((today.month + 2) / 3)

        return year, quarter, month

    def _get_period(self):
        if self.month is not None:  # monthly report
            period_start = datetime(self.year, self.month, 1, tzinfo=timezone.utc)
            period_end = (period_start + timedelta(days=32)).replace(day=1)
            return period_start, period_end

        if self.quarter == 1:
            period_start = datetime(self.year, 1, 1, tzinfo=timezone.utc)
            period_end = datetime(self.year, 4, 1, tzinfo=timezone.utc)
            return period_start, period_end

        if self.quarter == 2:
            period_start = datetime(self.year, 4, 1, tzinfo=timezone.utc)
            period_end = datetime(self.year, 7, 1, tzinfo=timezone.utc)
            return period_start, period_end

        if self.quarter == 3:
            period_start = datetime(self.year, 7, 1, tzinfo=timezone.utc)
            period_end = datetime(self.year, 10, 1, tzinfo=timezone.utc)
            return period_start, period_end

        if self.quarter == 4:
            period_start = datetime(self.year, 10, 1, tzinfo=timezone.utc)
            period_end = datetime(self.year + 1, 1, 1, tzinfo=timezone.utc)
            return period_start, period_end

        raise MossReportException(f"Invalid Quarter '{self.quarter}'")

    def _get_vatless_amount_per_country(self, countries, transactions):
        rates = ExchangeRate.objects.filter(
            year=self.year, quarter=self.quarter
        ).select_related('currency')
        rate_per_currency = {r.currency.code: r.rate for r in rates}
        vatless_amount_per_country = {}
        for country_code in countries:
            country = Country.objects.get(code=country_code)
            vatless_amount_per_country[country_code] = {
                'rate': country.vat_percentage_api(),
                'amount': Decimal(0),
            }

        for transaction in transactions:
            amount = transaction.amount
            vat = transaction.vat_amount
            currency_code = transaction.currency.code
            if currency_code == 'EUR':
                amount = amount - vat
            else:
                fx_rate = rate_per_currency.get(currency_code)
                if fx_rate is None:
                    raise MossReportException(
                        f'No FX rate available for {currency_code} {self.year} Q{self.quarter}'
                    )
                amount = (amount - vat) * fx_rate

            vatless_amount_per_country[transaction.country_id]['amount'] += amount

        return vatless_amount_per_country

    def _print_moss_file(self, vat_per_country, fileobj):
        moss_writer = csv.writer(
            fileobj,
            delimiter=';',
            lineterminator=';\n',
            quotechar='',
            quoting=csv.QUOTE_NONE,
        )
        moss_writer.writerow([CSV_HEADER_TITLE])
        # for monthly reports we use [MONTH][YEAR] as period
        # for quarterly reports we use [QUARTER][YEAR]
        period_identifier = self.month if self.month else self.quarter
        moss_writer.writerow([CSV_HEADER_ID, period_identifier, self.year])
        for country, vat_info in vat_per_country.items():
            if vat_info['amount'] > 0:
                vat_amount = vat_info['amount'] * vat_info['rate'] / Decimal(100)
                row = [
                    'SE',
                    MOSS_COUNTRY_LABELS.get(country, country),
                    f"{vat_info['rate']:.2f}".replace('.', ','),
                    f"{vat_info['amount']:.2f}".replace('.', ','),
                    f"{vat_amount:.2f}".replace('.', ','),
                ]
                moss_writer.writerow(row)
