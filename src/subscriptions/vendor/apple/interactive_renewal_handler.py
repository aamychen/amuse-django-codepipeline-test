from uuid import uuid4
from amuse.logging import logger
from django.utils import timezone
from django.http import HttpResponse
from rest_framework import status
from subscriptions.vendor.apple.commons import (
    process_receipt_extended,
    parse_timestamp_ms,
)

from payments.models import PaymentTransaction
from subscriptions.models import SubscriptionPlan, Subscription
from subscriptions.rules import Action, ChangeReason


class InteractiveRenewalHandler(object):
    """
    INTERACTIVE_RENEWAL
        Indicates the customer renewed a subscription interactively, either by using
        your app’s interface, or on the App Store in the account’s Subscriptions settings.
        Make service available immediately.
    """

    def __init__(self):
        self.txid = uuid4()
        self.n_name = 'INTERACTIVE_RENEWAL'

    def create_customer_payment_payload(self, country, latest_receipt):
        return {'country': country.code, 'receipt_data': latest_receipt}

    def expire_ugraded_subscription(self, next_to_last):
        next_to_last_payment = PaymentTransaction.objects.filter(
            external_transaction_id=next_to_last['transaction_id']
        ).last()
        sub_to_expire = next_to_last_payment.subscription
        next_to_last_payment.paid_until = timezone.now()
        next_to_last_payment.save()
        Action.expire(
            subscription=sub_to_expire,
            valid_until=timezone.now().date(),
            change_reason=ChangeReason.APPLE_INTERACTIVE_RENEWAL,
        )

    def handle_upgrade(self, last_tx, next_to_last, last_payment, last_receipt):
        try:
            original_transaction_id = last_tx['original_transaction_id']
            current_plan = SubscriptionPlan.objects.get_by_product_id(
                apple_product_id=last_tx['product_id']
            )
            last_payment_subscription = last_payment.subscription

            # Double notifications protection
            if (
                last_payment_subscription.plan.apple_product_id == last_tx['product_id']
                and last_payment_subscription.status == Subscription.STATUS_ACTIVE
            ):
                logger.info(
                    f'txid {self.txid} {self.n_name} subscription {last_payment_subscription.id} already upgraded {original_transaction_id}'
                )
                return HttpResponse(status=status.HTTP_200_OK)

            card = current_plan.get_price_card()
            # Create new payment and subscription
            sub = Action.create(
                plan=current_plan,
                payment_method=last_payment.payment_method,
                provider=Subscription.PROVIDER_IOS,
                change_reason=ChangeReason.APPLE_INTERACTIVE_RENEWAL,
            )

            PaymentTransaction.objects.create(
                amount=card.price,
                category=PaymentTransaction.CATEGORY_RENEWAL,
                country=last_payment.country,
                customer_payment_payload=self.create_customer_payment_payload(
                    last_payment.country, last_receipt
                ),
                external_transaction_id=last_tx['transaction_id'],
                paid_until=parse_timestamp_ms(last_tx['expires_date_ms']),
                payment_method=last_payment.payment_method,
                plan=current_plan,
                status=PaymentTransaction.STATUS_APPROVED,
                subscription=sub,
                type=PaymentTransaction.TYPE_PAYMENT,
                user=last_payment.user,
                vat_amount=last_payment.country.vat_amount(card.price),
                vat_percentage=last_payment.country.vat_percentage,
                currency=card.currency,
                platform=PaymentTransaction.PLATFORM_IOS,
            )

            # Cancel upgraded transaction
            # Expire upgraded subscription
            self.expire_ugraded_subscription(next_to_last=next_to_last)
            logger.info(
                f'txid {self.txid} {self.n_name} subscription {sub.id} UPGRADED to {current_plan.apple_product_id}'
            )
            return HttpResponse(status=status.HTTP_200_OK)

        except Exception as e:
            logger.warning(
                f'txid {self.txid} {self.n_name} upgrade FAILED with error {e} {original_transaction_id}'
            )
            return HttpResponse(status=status.HTTP_400_BAD_REQUEST)

    def handle(self, payload):
        try:
            details = process_receipt_extended(payload)
            last_transaction = details['last_transaction']
            last_transaction_id = last_transaction['transaction_id']
            pending_renewal_info = details['pending_renewals'][0]
            original_transaction_id = pending_renewal_info['original_transaction_id']
            current_product_id = last_transaction['product_id']
            is_upgrade = details['is_upgraded']
            next_to_last = details['next_to_last_transaction']

            current_plan = SubscriptionPlan.objects.get_by_product_id(
                apple_product_id=current_product_id
            )
            last_paymenet = (
                PaymentTransaction.objects.filter(
                    external_transaction_id__in=details['all_tx_ids']
                )
                .order_by("-created")
                .first()
            )
            if not last_paymenet:
                logger.warning(
                    f'txid {self.txid} {self.n_name} FAILED unable to find transactions original_tx_id {original_transaction_id}'
                )
                return HttpResponse(status=status.HTTP_400_BAD_REQUEST)

            if is_upgrade == 'true':
                return self.handle_upgrade(
                    last_tx=last_transaction,
                    next_to_last=next_to_last,
                    last_payment=last_paymenet,
                    last_receipt=details['latest_receipt'],
                )

            sub = last_paymenet.subscription
            card = current_plan.get_price_card()
            tx_exist = PaymentTransaction.objects.filter(
                external_transaction_id=last_transaction_id
            ).first()
            if not tx_exist:
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
                    plan=current_plan,
                    status=PaymentTransaction.STATUS_APPROVED,
                    subscription=sub,
                    type=PaymentTransaction.TYPE_PAYMENT,
                    user=last_paymenet.user,
                    vat_amount=last_paymenet.country.vat_amount(card.price),
                    vat_percentage=last_paymenet.country.vat_percentage,
                    currency=card.currency,
                    platform=PaymentTransaction.PLATFORM_IOS,
                )
                logger.info(
                    f'txid {self.txid} {self.n_name} {last_transaction_id} created new transaction'
                )
            sub.status = Subscription.STATUS_ACTIVE
            sub.valid_until = None
            sub.grace_period_until = None
            sub.plan = current_plan
            sub.save()
            logger.info(
                f'txid {self.txid} {self.n_name} subscription {sub.id} updated plan={current_plan.name} '
            )
            return HttpResponse(status=status.HTTP_200_OK)
        except Exception as e:
            logger.warning(
                f'txid {self.txid} {self.n_name} {last_transaction_id} FAILED with error {e}'
            )
            return HttpResponse(status=status.HTTP_400_BAD_REQUEST)
