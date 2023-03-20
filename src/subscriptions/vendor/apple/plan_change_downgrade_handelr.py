from uuid import uuid4
from django.utils import timezone
from amuse.logging import logger
from django.http import HttpResponse
from rest_framework import status
from subscriptions.vendor.apple.commons import (
    process_receipt_extended,
)

from payments.models import PaymentTransaction
from subscriptions.models import SubscriptionPlan


class PlanChangeDowgradeHandler(object):
    """
    DID_CHANGE_RENEWAL_PREF
        Indicates that the customer made a change in their subscription plan that
        takes effect at the next renewal. The currently active plan isn’t affected.

    """

    def __init__(self):
        self.txid = uuid4()
        self.n_name = 'DID_CHANGE_RENEWAL_PREF'

    def handle(self, payload):
        try:
            details = process_receipt_extended(payload)
            pending_renewal_info = details['pending_renewals'][0]
            original_transaction_id = pending_renewal_info['original_transaction_id']
            current_product_id = pending_renewal_info['product_id']
            new_product_id = pending_renewal_info['auto_renew_product_id']
            current_plan = SubscriptionPlan.objects.get_by_product_id(
                apple_product_id=current_product_id
            )
            new_plan = SubscriptionPlan.objects.get_by_product_id(
                apple_product_id=new_product_id
            )
            last_paymenet = (
                PaymentTransaction.objects.filter(
                    external_transaction_id__in=details['all_tx_ids']
                )
                .order_by("-created")
                .first()
            )
            sub = last_paymenet.subscription
            if new_plan.tier == current_plan.tier:
                logger.warning(
                    f'txid {self.txid} {self.n_name} crosssgrade plan change for org_tx_id={original_transaction_id} {current_product_id} -> {new_product_id}'
                )
                sub.plan = new_plan
                sub.save()
            if new_plan.tier < current_plan.tier:
                logger.warning(
                    f'txid {self.txid} {self.n_name} downgrade plan change for org_tx_id={original_transaction_id} {current_product_id} -> {new_product_id} plan will be changed on next renewal'
                )
            return HttpResponse(status=status.HTTP_200_OK)
        except Exception as e:
            logger.warning(
                f'txid {self.txid} {self.n_name} FAILED for {current_product_id} -> {new_product_id} org_tx_id={original_transaction_id} error {e} '
            )
            return HttpResponse(status=status.HTTP_400_BAD_REQUEST)
