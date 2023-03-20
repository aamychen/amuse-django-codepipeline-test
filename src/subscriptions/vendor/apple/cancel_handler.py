from uuid import uuid4
from django.utils import timezone
from amuse.logging import logger
from django.http import HttpResponse
from rest_framework import status
from subscriptions.vendor.apple.commons import (
    process_receipt_cancel,
)

from payments.models import PaymentTransaction
from subscriptions.rules import Action, ChangeReason
from subscriptions.models import Subscription


class CancelHandler(object):
    """
    CANCEL
    Indicates that either Apple customer support canceled the auto-renewable subscription
    or the user upgraded their auto-renewable subscription. The cancellation_date key
    contains the date and time of the change.
    Note: This event includes user being refunded by Apple Suport ??
    https://developer.apple.com/forums/thread/97019

    """

    def __init__(self):
        self.txid = uuid4()
        self.n_name = 'CANCEL'

    def handle(self, payload):
        details = process_receipt_cancel(payload)
        simple = details['simple_case']
        is_upgrade = details['is_upgrade']
        is_last_transaction_cancel = details['is_last_transaction_cancel']
        original_transaction_id = details['original_transaction'][
            'original_transaction_id'
        ]
        all_tx_ids = details['all_tx_ids']
        last_paymenet = (
            PaymentTransaction.objects.filter(external_transaction_id__in=all_tx_ids)
        ).last()
        if not last_paymenet:
            logger.warning(
                f'txid ={self.txid} {self.n_name} original_transaction {original_transaction_id} not  found in DB. Probably INITIAL_BUY failed.'
            )
            return HttpResponse(status=status.HTTP_200_OK)
        if is_last_transaction_cancel or simple:
            last_paymenet.status = PaymentTransaction.STATUS_CANCELED
            last_paymenet.save()
            sub = last_paymenet.subscription

            if sub.status not in [
                Subscription.STATUS_EXPIRED,
                Subscription.STATUS_ERROR,
            ]:
                Action.expire(
                    subscription=sub,
                    valid_until=timezone.now(),
                    change_reason=ChangeReason.APPLE_CANCELED,
                )
                logger.info(
                    f'txid ={self.txid} Apple {self.n_name} subscription_id {sub.id} expired.'
                )
        else:
            # There is a case when user makes double payments by mistake. In this case CANCEL and refund is issued but
            # there is no way for us to find affected transaction in out DB.
            logger.warning(
                f'txid ={self.txid} Apple {self.n_name} original_transaction {original_transaction_id} complex not implemeted'
            )

        return HttpResponse(status=status.HTTP_200_OK)
