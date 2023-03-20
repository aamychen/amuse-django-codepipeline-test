import logging
from datetime import datetime
from decimal import Decimal
from uuid import uuid4
from typing import Optional

from django.utils.timezone import make_aware
from payments.models import PaymentTransaction

from .enums import PaymentState

logger = logging.getLogger(__name__)


def debug(event_id, message):
    logger.debug(f'DEBUG :: GoogleBilling event={event_id}, message="{message}"')


def info(event_id, message):
    logger.info(f'INFO :: GoogleBilling event={event_id}, message="{message}"')


def error(event_id, message):
    logger.error(f'ERROR :: GoogleBilling Error event={event_id}, message="{message}"')


def exception(event_id, ex):
    logger.exception(
        f'EXCEPTION :: GoogleBilling Exception event={event_id}, exception="{ex}"'
    )


def warning(event_id, message):
    logger.warning(
        f'WARNING :: GoogleBilling Warning event={event_id}, message="{message}"'
    )


def convert_msepoch_to_dt(intvalue):
    """
    Converts 'the time in milliseconds since the epoch' to datetime.
    """

    dt = datetime.utcfromtimestamp(intvalue / 1000)
    return make_aware(dt)


def convert_microunits_to_currency_price(micro_units):
    """
    Price of the subscription is expressed in micro-units, where 1,000,000 micro-units
    represents one unit of the currency.

    For example, if the price is €1.99, microunit price is 1990000.
    """
    return Decimal(micro_units) / 1000000


def new_eventid():
    """
    Generate a random UUID as a string, without dashes.
    """
    return str(uuid4()).replace('-', '')


def payment_state_2_payment_transaction_status(payment_state: Optional[PaymentState]):
    mapper = {
        None: PaymentTransaction.TYPE_UNKNOWN,
        PaymentState.PENDING: PaymentTransaction.STATUS_PENDING,
        PaymentState.RECEIVED: PaymentTransaction.STATUS_APPROVED,
        PaymentState.FREE_TRIAL: PaymentTransaction.STATUS_APPROVED,
        # PaymentState.DEFERRED: PaymentTransaction.STATUS_ERROR,
    }

    return mapper.get(payment_state, PaymentTransaction.STATUS_ERROR)
