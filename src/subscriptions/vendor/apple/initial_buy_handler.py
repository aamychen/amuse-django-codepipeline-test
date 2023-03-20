from uuid import uuid4
from django.utils import timezone
from amuse.logging import logger
from django.http import HttpResponse
from rest_framework import status
from subscriptions.vendor.apple.commons import (
    process_receipt_simple,
)

from payments.models import PaymentTransaction
from subscriptions.models import Subscription


class InitialBuyHandelr(object):
    """
    INITIAL_BUY
    Occurs at the user’s initial purchase of the subscription.
    Store latest_receipt on your server as a token to verify the user’s subscription
    status at any time by validating it with the App Store.

    Once we get INITIAL_BUY notification transaction and subscription should exist in DB if not
    return 404 to apple so they resend it latter.
    Peform basic validation of subscription and transaction data.
    On success return 200 else 404
    """

    def __init__(self):
        self.txid = uuid4()
        self.n_name = 'INITIAL_BUY'

    def is_sub_data_correct(self, subscription, tx):
        status = subscription.status
        is_sub_active = status == Subscription.STATUS_ACTIVE
        is_tx_approved = tx.status = PaymentTransaction.STATUS_APPROVED
        return is_sub_active and is_tx_approved

    def handle(self, payload):
        details = process_receipt_simple(payload)
        payment = details['txs'][0]
        original_transaction_id = payment['original_transaction_id']
        tx = PaymentTransaction.objects.filter(
            external_transaction_id=original_transaction_id
        ).last()

        if not tx:
            logger.warning(
                f'txid ={self.txid} {self.n_name} {original_transaction_id} not found in DB'
            )
            return HttpResponse(status=status.HTTP_404_NOT_FOUND)
        sub = tx.subscription
        if self.is_sub_data_correct(sub, tx):
            return HttpResponse(status=status.HTTP_200_OK)
        logger.warning(
            f'txid ={self.txid} {self.n_name} {original_transaction_id} DB data validation failed'
        )
        return HttpResponse(status=status.HTTP_404_NOT_FOUND)
