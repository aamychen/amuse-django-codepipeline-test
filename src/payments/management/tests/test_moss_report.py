from decimal import Decimal
from io import StringIO
from unittest.mock import patch

from django.core.management import call_command
from django.test import TestCase
from django.utils.datetime_safe import datetime

from countries.models import ExchangeRate
from countries.tests.factories import CurrencyFactory, CountryFactory
from payments.services.moss import CSV_HEADER_ID, CSV_HEADER_TITLE, MOSS_COUNTRY_LABELS
from payments.tests.factories import PaymentTransactionFactory


class MossReportTestCase(TestCase):
    def setUp(self):
        # we will use Q1 of 2020 as the reference period for the test cases
        self.month = 1
        self.quarter = 1
        self.year = 2020
        self.currency = CurrencyFactory()
        self.country = CountryFactory(vat_percentage=Decimal(0.5))
        self.exchange_rate = ExchangeRate.objects.create(
            currency=self.currency, rate=1.5, year=self.year, quarter=self.quarter
        )

    def assert_csv_file_is_correct(self, transactions, csv_writer):
        """
        Helper method to assert if the output CSV file is formatted correctly and has
        correct calculations and final amounts

        For ease of use, we assume all transactions are using country and currency
        initiated above
        """

        csv_writer.writer.assert_called()
        csv_writer.writer().writerow.assert_any_call([CSV_HEADER_TITLE])
        self.assertEqual(csv_writer.writer().writerow.call_count, 3)

        amount = Decimal(0)
        for transaction in transactions:
            if self.currency.code == 'EUR':
                amount += transaction.amount - transaction.vat_amount
            else:
                amount += (transaction.amount - transaction.vat_amount) * Decimal(
                    self.exchange_rate.rate
                )

        csv_writer.writer().writerow.assert_called_with(
            [
                'SE',
                MOSS_COUNTRY_LABELS.get(self.country.code, self.country.code),
                f"{self.country.vat_percentage_api():.2f}".replace('.', ','),
                f"{amount:.2f}".replace('.', ','),
                f"{amount * self.country.vat_percentage_api() / Decimal(100):.2f}".replace(
                    '.', ','
                ),
            ]
        )

    @patch('payments.services.moss.csv')
    def test_calculation_is_correct(self, csv_writer_mock):
        amount = Decimal(10.0)
        with patch("amuse.tasks.zendesk_create_or_update_user"):
            # q1, included
            transaction = PaymentTransactionFactory(
                amount=amount,
                country=self.country,
                currency=self.currency,
                vat_amount=amount * self.country.vat_percentage,
            )
            transaction.created = datetime(self.year, self.month, 1)
            transaction.save()

            # q2, excluded
            transaction2 = PaymentTransactionFactory(
                amount=amount,
                country=self.country,
                currency=self.currency,
                vat_amount=amount * self.country.vat_percentage,
            )
            transaction2.created = datetime(self.year, 4, 1)
            transaction2.save()

            # q4 previous year, excluded
            transaction3 = PaymentTransactionFactory(
                amount=amount,
                country=self.country,
                currency=self.currency,
                vat_amount=amount * self.country.vat_percentage,
            )
            transaction3.created = datetime(self.year - 1, 12, 31)
            transaction3.save()

        call_command(
            "moss_report",
            country=self.country.code,
            year=self.year,
            quarter=self.quarter,
        )

        csv_writer_mock.writer().writerow.assert_any_call(
            [CSV_HEADER_ID, self.quarter, self.year]
        )
        self.assert_csv_file_is_correct([transaction], csv_writer_mock)

    @patch('payments.services.moss.csv')
    def test_calculation_is_correct_with_eur_currency(self, csv_writer_mock):
        self.currency.code = 'EUR'
        self.currency.save()
        amount = Decimal(10.0)
        with patch("amuse.tasks.zendesk_create_or_update_user"):
            transaction1 = PaymentTransactionFactory(
                amount=amount,
                country=self.country,
                currency=self.currency,
                vat_amount=amount * self.country.vat_percentage,
            )
            transaction1.created = datetime(self.year, self.month, 1)
            transaction1.save()

            transaction2 = PaymentTransactionFactory(
                amount=amount,
                country=self.country,
                currency=self.currency,
                vat_amount=amount * self.country.vat_percentage,
            )
            transaction2.created = datetime(self.year, self.month, 31)
            transaction2.save()

        call_command(
            "moss_report",
            country=self.country.code,
            year=self.year,
            quarter=self.quarter,
        )

        csv_writer_mock.writer().writerow.assert_any_call(
            [CSV_HEADER_ID, self.quarter, self.year]
        )
        self.assert_csv_file_is_correct([transaction1, transaction2], csv_writer_mock)

    @patch('payments.services.moss.csv')
    def test_monthly_report_is_correct(self, csv_writer_mock):
        amount = Decimal(10.0)
        with patch("amuse.tasks.zendesk_create_or_update_user"):
            # month correct, included
            transaction1 = PaymentTransactionFactory(
                amount=amount,
                country=self.country,
                currency=self.currency,
                vat_amount=amount * self.country.vat_percentage,
            )
            transaction1.created = datetime(self.year, self.month, 1)
            transaction1.save()

            # day before, excluded
            transaction2 = PaymentTransactionFactory(
                amount=amount,
                country=self.country,
                currency=self.currency,
                vat_amount=amount * self.country.vat_percentage,
            )
            transaction2.created = datetime(self.year - 1, 12, 31)
            transaction2.save()

            # day after, excluded
            transaction3 = PaymentTransactionFactory(
                amount=amount,
                country=self.country,
                currency=self.currency,
                vat_amount=amount * self.country.vat_percentage,
            )
            transaction3.created = datetime(self.year, self.month + 1, 1)
            transaction3.save()

            # last day of month at 23:59:59, included
            transaction4 = PaymentTransactionFactory(
                amount=amount,
                country=self.country,
                currency=self.currency,
                vat_amount=amount * self.country.vat_percentage,
            )
            transaction4.created = datetime(self.year, self.month, 31, 23, 59, 59)
            transaction4.save()

        call_command(
            "moss_report", country=self.country.code, year=self.year, month=self.month
        )

        csv_writer_mock.writer().writerow.assert_any_call(
            [CSV_HEADER_ID, self.month, self.year]
        )
        self.assert_csv_file_is_correct([transaction1, transaction4], csv_writer_mock)

    def test_invalid_quarter_exits_and_err_logs(self):
        out = StringIO()

        with self.assertRaises(SystemExit):
            call_command(
                "moss_report",
                country=self.country.code,
                year=self.year,
                quarter=0,
                stderr=out,
            )
        self.assertIn("Invalid Quarter '0'", out.getvalue())

    def test_invalid_month_exits_and_err_logs(self):
        out = StringIO()

        with self.assertRaises(SystemExit):
            call_command(
                "moss_report",
                country=self.country.code,
                year=self.year,
                quarter=self.quarter,
                month=0,
                stderr=out,
            )
        self.assertIn('Invalid month number entered: 0', out.getvalue())

    def test_missing_fx_rate_exits_and_err_logs(self):
        out = StringIO()
        ExchangeRate.objects.all().delete()

        amount = Decimal(10.0)
        with patch("amuse.tasks.zendesk_create_or_update_user"):
            transaction = PaymentTransactionFactory(
                amount=amount,
                country=self.country,
                currency=self.currency,
                vat_amount=amount * self.country.vat_percentage,
            )
            transaction.created = datetime(self.year, self.month, 1)
            transaction.save()

        with self.assertRaises(SystemExit):
            call_command(
                "moss_report",
                country=self.country.code,
                year=self.year,
                quarter=self.quarter,
                stderr=out,
            )
        self.assertIn('No FX rate available for', out.getvalue())

    @patch('payments.services.moss.csv')
    def test_month_argument_present_ignores_quarter_argument(self, csv_writer_mock):
        quarter = 4
        amount = Decimal(10.0)
        with patch("amuse.tasks.zendesk_create_or_update_user"):
            transaction1 = PaymentTransactionFactory(
                amount=amount,
                country=self.country,
                currency=self.currency,
                vat_amount=amount * self.country.vat_percentage,
            )
            transaction2 = PaymentTransactionFactory(
                amount=amount,
                country=self.country,
                currency=self.currency,
                vat_amount=amount * self.country.vat_percentage,
            )

            transaction1.created = datetime(self.year, self.month, 1)
            transaction1.save()
            transaction2.created = datetime(self.year, 12, 1)
            transaction2.save()

        call_command(
            "moss_report",
            country=self.country.code,
            year=self.year,
            quarter=quarter,  # quarter is 4 so transaction2 should be included
            month=self.month,  # but month kwarg is present, so transaction2 is ignored
        )

        csv_writer_mock.writer().writerow.assert_any_call(
            [CSV_HEADER_ID, self.month, self.year]
        )
        self.assert_csv_file_is_correct([transaction1], csv_writer_mock)
