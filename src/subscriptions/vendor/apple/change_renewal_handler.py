from uuid import uuid4
from amuse.logging import logger
from django.http import HttpResponse
from rest_framework import status
from subscriptions.vendor.apple.commons import (
    process_receipt_extended,
)
from payments.models import PaymentTransaction


class ChangeRenewalHandler(object):
    """
    DID_CHANGE_RENEWAL_STATUS
        Indicates a change in the subscription renewal status. In the JSON response,
        check auto_renew_status_change_date_ms to know the date and time of
        the last status update. Check auto_renew_status to know the current renewal status.
    """

    def __init__(self):
        self.txid = uuid4()
        self.n_name = 'DID_CHANGE_RENEWAL_STATUS'

    def handle(self, payload):
        details = process_receipt_extended(payload)
        pending_renewal_info = details['pending_renewals'][0]
        auto_renew_status = pending_renewal_info['auto_renew_status']
        original_transaction_id = pending_renewal_info['original_transaction_id']
        all_txs_ids = details['all_tx_ids']
        tx = PaymentTransaction.objects.filter(
            external_transaction_id__in=all_txs_ids
        ).last()

        if not tx:
            logger.warning(
                f'txid ={self.txid} {self.n_name} {original_transaction_id} not found in DB'
            )
            return HttpResponse(status=status.HTTP_404_NOT_FOUND)

        sub = tx.subscription
        if auto_renew_status == '0':
            sub.valid_until = tx.paid_until
            sub.save()
        if auto_renew_status == '1':
            sub.valid_until = None
            sub.save()
        logger.info(
            f'txid {self.txid} {self.n_name} auto_renew_status = {auto_renew_status} org_tx_id {original_transaction_id} changed.'
        )
        return HttpResponse(status=status.HTTP_200_OK)
