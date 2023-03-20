import datetime
from decimal import Decimal
from unittest import TestCase
from unittest.mock import patch

import pytest
import responses
from django.core.management import call_command

from amuse.vendor.currencylayer import CurrencyLayer
from countries.tests.factories import CurrencyFactory, CountryFactory
from payments.models import PaymentTransaction
from payments.tests.factories import PaymentTransactionFactory
from subscriptions.models import Subscription


class TestVatSekBackfillCurrencyLayerCommand(TestCase):
    def setUp(self):
        self.currency = CurrencyFactory(code='XYZ')
        self.country = CountryFactory(vat_percentage=Decimal(0.5))
        self.start_of_the_year = datetime.date(datetime.date.today().year, 1, 1)

    @responses.activate
    @pytest.mark.django_db
    @patch('amuse.tasks.zendesk_create_or_update_user')
    @patch.object(CurrencyLayer, 'convert', return_value=Decimal('12.34'))
    def test_exchange_done(self, mock_conversion, __):
        self.payment = PaymentTransactionFactory(
            subscription__plan__trial_days=0,
            subscription__provider=Subscription.PROVIDER_ADYEN,
            currency__code='XYZ',
            vat_amount=Decimal('10.20'),
            status=PaymentTransaction.STATUS_APPROVED,
        )

        call_command(
            'vat_sek_backfill_currency_layer', f'--start_date={self.start_of_the_year}'
        )
        mock_conversion.assert_called_once()

    @responses.activate
    @pytest.mark.django_db
    @patch('amuse.tasks.zendesk_create_or_update_user')
    @patch.object(CurrencyLayer, 'convert', return_value=Decimal('12.34'))
    def test_exchange_sek(self, mock_conversion, __):
        self.payment = PaymentTransactionFactory(
            subscription__plan__trial_days=0,
            subscription__provider=Subscription.PROVIDER_ADYEN,
            currency__code='SEK',
            vat_amount=Decimal('10.20'),
            status=PaymentTransaction.STATUS_APPROVED,
        )
        call_command(
            'vat_sek_backfill_currency_layer', f'--start_date={self.start_of_the_year}'
        )
        self.assertEqual(0, mock_conversion.call_count)

    @responses.activate
    @pytest.mark.django_db
    @patch('amuse.tasks.zendesk_create_or_update_user')
    @patch.object(CurrencyLayer, 'convert', return_value=Decimal('12.34'))
    def test_exchange_zero(self, mock_conversion, __):
        self.payment = PaymentTransactionFactory(
            subscription__plan__trial_days=0,
            subscription__provider=Subscription.PROVIDER_ADYEN,
            currency__code='EUR',
            vat_amount=Decimal('0'),
            status=PaymentTransaction.STATUS_APPROVED,
        )
        call_command(
            'vat_sek_backfill_currency_layer', f'--start_date={self.start_of_the_year}'
        )
        self.assertEqual(0, mock_conversion.call_count)

    @responses.activate
    @pytest.mark.django_db
    @patch('amuse.tasks.zendesk_create_or_update_user')
    @patch.object(CurrencyLayer, 'convert', side_effect=[Decimal('12.34'), None])
    def test_exchange_stop_if_conversion_fails(self, mock_conversion, __):
        for i in range(0, 5):
            PaymentTransactionFactory(
                subscription__plan__trial_days=0,
                subscription__provider=Subscription.PROVIDER_ADYEN,
                currency__code='EUR',
                vat_amount=Decimal('12.34'),
                status=PaymentTransaction.STATUS_APPROVED,
            )

        call_command(
            'vat_sek_backfill_currency_layer', f'--start_date={self.start_of_the_year}'
        )
        self.assertEqual(2, mock_conversion.call_count)
