from uuid import uuid4
from django.utils import timezone
from amuse.logging import logger
from django.http import HttpResponse
from rest_framework import status
from subscriptions.vendor.apple.commons import (
    process_receipt_extended,
)

from payments.models import PaymentTransaction
from subscriptions.models import Subscription, SubscriptionPlan


class RenewHandler(object):
    """
    Handler for following notifications:
        DID_RENEW
        DID_RECOVER
        RENEWAL (Apple will remove it in March 2021)
    All this notifications indicates that success auto renew happen
    we need to create new payment record for subscription and to set subscription to Active

        DID_FAIL_TO_RENEW
    Indicates a subscription that failed to renew due to a billing issue.
    Check is_in_billing_retry_period to know the current retry status of the
    subscription. Check grace_period_expires_date to know the new service
    expiration date if the subscription is in a billing grace period.

    """

    def __init__(self):
        self.txid = uuid4()
        self.n_name = None

    def set_n_name(self, payload):
        self.n_name = payload.get('notification_type')

    def create_customer_payment_payload(self, country, latest_receipt):
        return {'country': country.code, 'receipt_data': latest_receipt}

    def transaction_exist(self, transaction_id):
        tx = PaymentTransaction.objects.filter(external_transaction_id=transaction_id)
        if not tx:
            return False
        return True

    def handle_failed_to_renew(self, last_payment, subscription, pending_renewal_info):
        apple_will_retry = pending_renewal_info['is_in_billing_retry_period']
        org_tx_id = pending_renewal_info['original_transaction_id']
        if apple_will_retry == '1':
            logger.info(
                f'txid {self.txid} {self.n_name} {org_tx_id} subscription {subscription.id} in Apple retry period'
            )
            subscription.valid_until = last_payment.paid_until
            subscription.save()
        if apple_will_retry == '0':
            logger.info(
                f'txid {self.txid} {self.n_name} {org_tx_id} subscription {subscription.id} expired'
            )
            subscription.valid_until = last_payment.paid_until
            subscription.status = Subscription.STATUS_EXPIRED
            subscription.save()
        return HttpResponse(status=status.HTTP_200_OK)

    def handle(self, payload):
        self.set_n_name(payload)
        try:
            details = process_receipt_extended(payload)
            pending_renewal_info = details['pending_renewals'][0]
            org_tx_id = pending_renewal_info['original_transaction_id']
            last_paymenet = (
                PaymentTransaction.objects.filter(
                    external_transaction_id__in=details['all_tx_ids']
                )
                .order_by("-created")
                .first()
            )
            sub = last_paymenet.subscription
            if self.n_name == 'DID_FAIL_TO_RENEW':
                return self.handle_failed_to_renew(
                    last_payment=last_paymenet,
                    subscription=sub,
                    pending_renewal_info=pending_renewal_info,
                )

            plan = SubscriptionPlan.objects.get_by_product_id(
                details['last_transaction']['product_id']
            )
            if not self.transaction_exist(
                details['last_transaction']['transaction_id']
            ):
                card = plan.get_price_card()
                PaymentTransaction.objects.create(
                    amount=card.price,
                    category=PaymentTransaction.CATEGORY_RENEWAL,
                    country=last_paymenet.country,
                    customer_payment_payload=self.create_customer_payment_payload(
                        last_paymenet.country, details['latest_receipt']
                    ),
                    external_transaction_id=details['last_transaction'][
                        'transaction_id'
                    ],
                    paid_until=details['last_expires_date'],
                    payment_method=last_paymenet.payment_method,
                    plan=plan,
                    status=PaymentTransaction.STATUS_APPROVED,
                    subscription=sub,
                    type=PaymentTransaction.TYPE_PAYMENT,
                    user=last_paymenet.user,
                    vat_amount=last_paymenet.country.vat_amount(card.price),
                    vat_percentage=last_paymenet.country.vat_percentage,
                    currency=card.currency,
                    platform=PaymentTransaction.PLATFORM_IOS,
                )
            sub.status = Subscription.STATUS_ACTIVE
            sub.plan = plan
            sub.valid_until = None
            sub.grace_period_until = None
            sub.save()
            logger.info(
                f'txid {self.txid} SUCCESS for Apple {self.n_name} and subscription {sub.id}'
            )
            return HttpResponse(status=status.HTTP_200_OK)
        except Exception as e:
            logger.warning(
                f'txid {self.txid} FAILED for Apple {self.n_name} org_tx_id {org_tx_id} with error {e}'
            )
            return HttpResponse(status=status.HTTP_400_BAD_REQUEST)
