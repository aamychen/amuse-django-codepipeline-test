import pytest

from datetime import datetime
from decimal import Decimal
from unittest import mock

from django.test import TestCase
from django.utils.timezone import make_aware
from payments.models import PaymentTransaction
from subscriptions.vendor.google import helpers
from subscriptions.vendor.google.enums import PaymentState


class TestHelpers(TestCase):
    @mock.patch('subscriptions.vendor.google.helpers.uuid4', return_value='123-456')
    def test_new_event_id(self, _):
        result = helpers.new_eventid()
        self.assertEqual('123456', result)

    @mock.patch('subscriptions.vendor.google.helpers.logger.debug')
    def test_debug(self, mock_logger):
        helpers.debug('123', 'debug message')
        mock_logger.assert_called_once_with(
            'DEBUG :: GoogleBilling event=123, message="debug message"'
        )

    @mock.patch('subscriptions.vendor.google.helpers.logger.info')
    def test_info(self, mock_logger):
        helpers.info('123', 'info message')
        mock_logger.assert_called_once_with(
            'INFO :: GoogleBilling event=123, message="info message"'
        )

    @mock.patch('subscriptions.vendor.google.helpers.logger.warning')
    def test_warning(self, mock_logger):
        helpers.warning('123', 'warning message')
        mock_logger.assert_called_once_with(
            'WARNING :: GoogleBilling Warning event=123, message="warning message"'
        )

    @mock.patch('subscriptions.vendor.google.helpers.logger.error')
    def test_error(self, mock_logger):
        helpers.error('123', 'error message')
        mock_logger.assert_called_once_with(
            'ERROR :: GoogleBilling Error event=123, message="error message"'
        )

    @mock.patch('subscriptions.vendor.google.helpers.logger.exception')
    def test_exception(self, mock_logger):
        helpers.exception('123', Exception('exception message'))
        mock_logger.assert_called_once_with(
            'EXCEPTION :: GoogleBilling Exception event=123, exception="exception message"'
        )

    def test_convert_msepoch_to_dt(self):
        result = helpers.convert_msepoch_to_dt(int('1610467867668'))
        self.assertEqual(result, make_aware(datetime(2021, 1, 12, 16, 11, 7, 668000)))

    def test_convert_microunits_to_currency_price(self):
        result = helpers.convert_microunits_to_currency_price(1990000)
        self.assertEqual(result, Decimal('1.99'))


@pytest.mark.parametrize(
    "input_payment_state, expected_transaction_state",
    [
        (None, PaymentTransaction.TYPE_UNKNOWN),
        (PaymentState.PENDING, PaymentTransaction.STATUS_PENDING),
        (PaymentState.RECEIVED, PaymentTransaction.STATUS_APPROVED),
        (PaymentState.FREE_TRIAL, PaymentTransaction.STATUS_APPROVED),
        (PaymentState.DEFERRED, PaymentTransaction.STATUS_ERROR),
    ],
)
def test_payment_state_2_payment_transaction_status(
    input_payment_state, expected_transaction_state
):
    actual = helpers.payment_state_2_payment_transaction_status(input_payment_state)
    assert expected_transaction_state == actual
