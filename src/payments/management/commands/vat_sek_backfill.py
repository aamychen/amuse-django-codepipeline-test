import decimal
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional

import requests
from django.core.management.base import BaseCommand

from payments.models import PaymentTransaction
from subscriptions.models import Subscription

CURRENCY_SEK = 'SEK'


class ERH:
    def __init__(self):
        self.client = requests.Session()

    @staticmethod
    def format_date(date):
        return date.strftime("%Y-%m-%d")

    def convert_historical(
        self, from_currency, amount, date
    ) -> (Optional[Decimal], bool):
        endpoint = f'https://api.exchangerate.host/convert'
        params = {
            'from': from_currency,
            'to': CURRENCY_SEK,
            'amount': amount,
            'date': self.format_date(date),
            'places': 4,
        }

        response = self.client.get(endpoint, params=params, timeout=10)
        response.raise_for_status()

        result = response.json(parse_int=decimal.Decimal, parse_float=decimal.Decimal)

        if result.get('success') is False:
            return None, False

        should_run_again = int(response.headers['x-ratelimit-remaining']) > 0

        return result.get('result', None), should_run_again


class Command(BaseCommand):
    """
    The ExchangeRate.Host API is used to populate the vat amount sek property.
    ExchangeRate.host API is a simple and lightweight free service for current and historical foreign exchange rates.
    Because it is free, there is no certainty that it will always work.
    Throttling/rate limit rules are also unclear.

    There are about 100k transactions that must be backfilled.
    We will run this command on a regular basis, attempting to backfill ~2k transactions each time.
    """

    def info(self, *args):
        msg = '\t'.join(str(x) for x in args)
        self.stdout.write(msg)

    @staticmethod
    def round(amount):
        if amount is None:
            return None

        return amount.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

    def calculate_vat_amount_sek(
        self, payment: PaymentTransaction, exchange: ERH
    ) -> (Optional[Decimal], bool):
        if payment.currency.code == CURRENCY_SEK:
            return payment.vat_amount, True

        vat_sek, should_run_again = exchange.convert_historical(
            payment.currency.code, payment.vat_amount, payment.created
        )

        return self.round(vat_sek), should_run_again

    def handle(self, *args, **kwargs):
        payments = (
            PaymentTransaction.objects.filter(
                status=PaymentTransaction.STATUS_APPROVED,
                subscription__provider=Subscription.PROVIDER_ADYEN,
                vat_amount__gt=0,
                vat_amount_sek__isnull=True,
            )
            .order_by('-id')
            .all()[:2000]
        )
        self.info(f'Total payments: {payments.count()}')

        self.info(payments.query)

        exchange = ERH()
        for i, p in enumerate(payments):
            vat_amount_sek, run_again = self.calculate_vat_amount_sek(p, exchange)
            if vat_amount_sek is None:
                self.info("Unable to proceed. Execution will stop.")
                return

            p.vat_amount_sek = vat_amount_sek
            p.save()

            values = [
                i,
                p.id,
                p.currency.code,
                p.country,
                p.amount,
                p.vat_amount,
                p.vat_amount_sek,
                p.created.strftime("%Y-%m-%d %H:%M"),
            ]
            self.info('\t'.join(str(x) for x in values))

            if not run_again:
                self.info("Rate Limit reached. Execution will stop.")
                return

        self.info("Command completed")
