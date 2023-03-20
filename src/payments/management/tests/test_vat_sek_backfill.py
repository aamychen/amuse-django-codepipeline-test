import datetime
from decimal import Decimal
from unittest import TestCase
from unittest.mock import patch

import pytest
import responses
from django.core.management import call_command
from requests import Session
from requests.exceptions import HTTPError

from countries.tests.factories import CurrencyFactory, CountryFactory
from payments.management.commands.vat_sek_backfill import ERH
from payments.models import PaymentTransaction
from payments.tests.factories import PaymentTransactionFactory
from subscriptions.models import Subscription


class MockResponse:
    def __init__(self, result, success=True, status_code=200, rate_limit=10):
        self.result = result
        self.status_code = status_code
        self.success = success
        self.headers = {'x-ratelimit-remaining': rate_limit}

    def json(self, parse_int, parse_float):
        return {"success": self.success, 'result': Decimal(self.result)}

    def raise_for_status(self):
        if 200 <= self.status_code < 300:
            return

        raise HTTPError('Http Error')


class TestERH(TestCase):
    @pytest.mark.django_db
    @patch.object(Session, 'get', return_value=MockResponse('12.35'))
    def test_client(self, mock_get):
        actual, run_again = ERH().convert_historical(
            from_currency='ABC', amount=Decimal('1.23'), date=datetime.date(2021, 8, 2)
        )

        mock_get.assert_called_once()
        self.assertEqual(Decimal('12.35'), actual)
        self.assertTrue(run_again)

    @pytest.mark.django_db
    @patch.object(Session, 'get', return_value=MockResponse('12.35', rate_limit=0))
    def test_client_rate_limit_reached(self, mock_get):
        actual, run_again = ERH().convert_historical(
            from_currency='ABC', amount=Decimal('1.23'), date=datetime.date(2021, 8, 2)
        )

        mock_get.assert_called_once()
        self.assertEqual(Decimal('12.35'), actual)
        self.assertFalse(run_again)

    @pytest.mark.django_db
    @patch.object(Session, 'get', return_value=MockResponse('1.23', success=False))
    def test_client_invalid_result(self, mock_get):
        actual, run_again = ERH().convert_historical(
            from_currency='ABC', amount=Decimal('1.23'), date=datetime.date(2021, 8, 2)
        )

        mock_get.assert_called_once()
        self.assertIsNone(actual)
        self.assertFalse(run_again)

    @pytest.mark.django_db
    @patch.object(Session, 'get', return_value=MockResponse('1.23', status_code=500))
    def test_client_invalid_response(self, _):
        with pytest.raises(HTTPError):
            ERH().convert_historical(
                from_currency='ABC',
                amount=Decimal('1.23'),
                date=datetime.date(2021, 8, 2),
            )


class TestVatSekBackfillCommand(TestCase):
    def setUp(self):
        self.currency = CurrencyFactory(code='XYZ')
        self.country = CountryFactory(vat_percentage=Decimal(0.5))

    @responses.activate
    @pytest.mark.django_db
    @patch('amuse.tasks.zendesk_create_or_update_user')
    @patch.object(ERH, 'convert_historical', return_value=(Decimal('12.34'), True))
    def test_exchange_done(self, mock_conversion, __):
        self.payment = PaymentTransactionFactory(
            subscription__plan__trial_days=0,
            subscription__provider=Subscription.PROVIDER_ADYEN,
            currency__code='XYZ',
            vat_amount=Decimal('10.20'),
            status=PaymentTransaction.STATUS_APPROVED,
        )
        call_command('vat_sek_backfill')
        mock_conversion.assert_called_once()

    @responses.activate
    @pytest.mark.django_db
    @patch('amuse.tasks.zendesk_create_or_update_user')
    @patch.object(ERH, 'convert_historical', return_value=(Decimal('12.34'), True))
    def test_exchange_sek(self, mock_conversion, __):
        self.payment = PaymentTransactionFactory(
            subscription__plan__trial_days=0,
            subscription__provider=Subscription.PROVIDER_ADYEN,
            currency__code='SEK',
            vat_amount=Decimal('10.20'),
            status=PaymentTransaction.STATUS_APPROVED,
        )
        call_command('vat_sek_backfill')
        self.assertEqual(0, mock_conversion.call_count)

    @responses.activate
    @pytest.mark.django_db
    @patch('amuse.tasks.zendesk_create_or_update_user')
    @patch.object(ERH, 'convert_historical', return_value=(Decimal('12.34'), True))
    def test_exchange_zero(self, mock_conversion, __):
        self.payment = PaymentTransactionFactory(
            subscription__plan__trial_days=0,
            subscription__provider=Subscription.PROVIDER_ADYEN,
            currency__code='EUR',
            vat_amount=Decimal('0'),
            status=PaymentTransaction.STATUS_APPROVED,
        )
        call_command('vat_sek_backfill')
        self.assertEqual(0, mock_conversion.call_count)

    @responses.activate
    @pytest.mark.django_db
    @patch('amuse.tasks.zendesk_create_or_update_user')
    @patch.object(
        ERH,
        'convert_historical',
        side_effect=[
            (Decimal('12.34'), True),
            (Decimal('12.34'), True),
            (Decimal('12.34'), False),
        ],
    )
    def test_exchange_stop_on_rate_limit(self, mock_conversion, __):
        for i in range(0, 5):
            PaymentTransactionFactory(
                subscription__plan__trial_days=0,
                subscription__provider=Subscription.PROVIDER_ADYEN,
                currency__code='EUR',
                vat_amount=Decimal('12.34'),
                status=PaymentTransaction.STATUS_APPROVED,
            )

        call_command('vat_sek_backfill')
        self.assertEqual(3, mock_conversion.call_count)

    @responses.activate
    @pytest.mark.django_db
    @patch('amuse.tasks.zendesk_create_or_update_user')
    @patch.object(
        ERH, 'convert_historical', side_effect=[(Decimal('12.34'), True), (None, True)]
    )
    def test_exchange_stop_if_conversion_fails(self, mock_conversion, __):
        for i in range(0, 5):
            PaymentTransactionFactory(
                subscription__plan__trial_days=0,
                subscription__provider=Subscription.PROVIDER_ADYEN,
                currency__code='EUR',
                vat_amount=Decimal('12.34'),
                status=PaymentTransaction.STATUS_APPROVED,
            )

        call_command('vat_sek_backfill')
        self.assertEqual(2, mock_conversion.call_count)
