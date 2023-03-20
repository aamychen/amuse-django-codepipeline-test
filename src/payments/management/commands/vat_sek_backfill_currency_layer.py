from datetime import datetime, date
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional

from django.core.management.base import BaseCommand

from amuse.vendor.currencylayer import CurrencyLayer
from payments.models import PaymentTransaction
from subscriptions.models import Subscription

CURRENCY_SEK = 'SEK'


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument('--start_date')
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Just print, do not update',
            default=False,
        )

    def info(self, *args):
        msg = '\t'.join(str(x) for x in args)
        self.stdout.write(msg)

    @staticmethod
    def round(amount):
        if amount is None:
            return None

        return amount.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

    def calculate_vat_amount_sek(
        self, payment: PaymentTransaction, exchange: CurrencyLayer
    ) -> (Optional[Decimal], bool):
        if payment.currency.code == CURRENCY_SEK:
            return payment.vat_amount

        dt = payment.created.strftime('%Y-%m-%d')
        currency_code = payment.currency.code
        vat_amount = payment.vat_amount
        vat_sek = exchange.convert(currency_code, CURRENCY_SEK, vat_amount, dt)

        return self.round(vat_sek)

    def handle(self, start_date, **kwargs):
        if start_date is None:
            start_date = date(datetime.today().year, 1, 1)
        else:
            start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
        dry_run = kwargs.get("dry_run", False)

        self.info('start_date', start_date)
        self.info('dry_run', dry_run)

        payments = PaymentTransaction.objects.filter(
            subscription__provider=Subscription.PROVIDER_ADYEN,
            vat_amount__gt=0,
            vat_amount_sek__isnull=True,
            created__gte=start_date,
        )

        self.info(f'Total payments: {payments.count()}')

        self.info(payments.query)

        labels = [
            'idx',
            'id',
            'curr.',
            'country',
            'amount',
            'vat',
            'vat_sek',
            'created',
        ]
        self.info('\t'.join(str(x) for x in labels))

        exchange = CurrencyLayer()
        for i, p in enumerate(payments):
            vat_amount_sek = self.calculate_vat_amount_sek(p, exchange)
            if vat_amount_sek is None:
                self.info("Unable to proceed. Execution will stop.")
                return

            p.vat_amount_sek = vat_amount_sek
            if not dry_run:
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

        self.info("Command completed")
