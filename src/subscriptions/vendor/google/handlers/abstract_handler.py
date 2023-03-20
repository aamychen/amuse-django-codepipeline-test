from abc import ABC, abstractmethod
from functools import cmp_to_key
from typing import Optional
from datetime import datetime
from decimal import Decimal

from countries.models import Country, Currency
from payments.models import PaymentMethod, PaymentTransaction
from subscriptions.models import Subscription, SubscriptionPlan
from .containers import HandlerArgs
from ..enums import AcknowledgementState, ProcessingResult, SubscriptionNotificationType
from ..errors import (
    PaymentMethodNotFoundError,
    PaymentTransactionNotFoundError,
    SubscriptionPlanNotFoundError,
    SubscriptionNotFoundError,
    SubscriptionsMultipleActiveError,
    SubscriptionsMultipleActivePurchaseTokenError,
)
from ..helpers import info, payment_state_2_payment_transaction_status


class AbstractNotificationHandler(ABC):
    def __init__(self, event_id):
        self.event_id = event_id

    def log(self, data: HandlerArgs):
        info(
            self.event_id,
            f'NotificationType: {SubscriptionNotificationType(data.notification_type).name}',
        )

    @staticmethod
    def get_active_subscription_by_user(user_id: int) -> Optional[Subscription]:
        subscriptions = list(
            Subscription.objects.filter(
                user_id=user_id,
                provider=Subscription.PROVIDER_GOOGLE,
                status__in=[
                    Subscription.STATUS_ACTIVE,
                    Subscription.STATUS_GRACE_PERIOD,
                ],
            )
        )

        if len(subscriptions) > 1:
            sub_ids = [s.id for s in subscriptions]
            raise SubscriptionsMultipleActiveError(user_id, sub_ids)

        return subscriptions[0] if subscriptions else None

    @staticmethod
    def get_active_subscription_by_token(purchase_token: str) -> Optional[Subscription]:
        subscriptions = list(
            Subscription.objects.filter(
                payment_method__external_recurring_id=purchase_token,
                provider=Subscription.PROVIDER_GOOGLE,
                status__in=[
                    Subscription.STATUS_ACTIVE,
                    Subscription.STATUS_GRACE_PERIOD,
                ],
            )
        )

        if len(subscriptions) > 1:
            sub_ids = [s.id for s in subscriptions]
            raise SubscriptionsMultipleActivePurchaseTokenError(purchase_token, sub_ids)

        return subscriptions[0] if subscriptions else None

    @staticmethod
    def get_handleable_subscription(data: HandlerArgs) -> Subscription:
        """
        Handleable subscription status can be: [ACTIVE, GRACE_PERIOD, EXPIRED].
        Result of this method should be used for comparison (e.g. to determine if
        subscription is EXPIRED, and never used to alter the subscription (e.g. to
        change the status).
        """
        subscriptions = list(
            Subscription.objects.filter(
                payment_method__external_recurring_id=data.purchase_token,
                provider=Subscription.PROVIDER_GOOGLE,
                status__in=[
                    Subscription.STATUS_ACTIVE,
                    Subscription.STATUS_GRACE_PERIOD,
                    Subscription.STATUS_EXPIRED,
                ],
            )
        )

        if len(subscriptions) == 0:
            raise SubscriptionNotFoundError(data.purchase_token)

        # sort is required. we want to get the most recent and most valid subscription.
        # this array can contain EXPIRED and ACTIVE and IN_GRACE_PERIOD subs
        subscriptions.sort(key=cmp_to_key(subscription_comparator))

        return subscriptions[0]

    @staticmethod
    def get_payment_method(data: HandlerArgs) -> PaymentMethod:
        payment_method = PaymentMethod.objects.filter(
            external_recurring_id=data.purchase_token
        ).first()

        if payment_method is None:
            raise PaymentMethodNotFoundError(data.purchase_token)

        return payment_method

    @staticmethod
    def get_payment_transaction(
        data: HandlerArgs, raise_exception=True
    ) -> PaymentTransaction:
        """
        Find payment transaction by external_transaction_id.
        Args:
            data: input data
            raise_exception: will raise PaymentTransactionNotFoundError exception if PaymentTransaction does not exist

        Returns:
            PaymentTransaction
        """
        order_id = data.purchase.order_id
        payment = PaymentTransaction.objects.filter(
            external_transaction_id=order_id
        ).first()

        if payment is None and raise_exception:
            raise PaymentTransactionNotFoundError(order_id)

        return payment

    @staticmethod
    def get_plan(data: HandlerArgs) -> SubscriptionPlan:
        google_sub_id = data.google_subscription_id
        plan = SubscriptionPlan.objects.get_by_google_product_id(google_sub_id)

        if plan is None:
            raise SubscriptionPlanNotFoundError(google_sub_id)

        return plan

    @staticmethod
    def get_price(data: HandlerArgs):
        purchase = data.purchase
        if purchase.acknowledgement_state == AcknowledgementState.ACKNOWLEDGED:
            return purchase.price_amount

        return Decimal('0.0')

    def payment_transaction_new(self, subscription: Subscription, data: HandlerArgs):
        plan = self.get_plan(data)
        payment_method = self.get_payment_method(data)

        purchase = data.purchase

        paid_until = purchase.expiry_date
        price = self.get_price(data)

        country = Country.objects.filter(code=purchase.country_code.upper()).first()
        currency = Currency.objects.filter(
            code=purchase.price_currency_code.upper()
        ).first()

        status = payment_state_2_payment_transaction_status(purchase.payment_state)

        tx = PaymentTransaction.objects.create(
            amount=price,
            category=PaymentTransaction.CATEGORY_RENEWAL,
            country=country,
            customer_payment_payload=None,
            external_payment_response=purchase.payload,
            external_transaction_id=purchase.order_id,
            paid_until=paid_until,
            payment_method=payment_method,
            plan=plan,
            status=status,
            subscription=subscription,
            type=PaymentTransaction.TYPE_PAYMENT,
            user=subscription.user,
            vat_amount=0,
            vat_percentage=0,
            currency=currency,
            platform=PaymentTransaction.PLATFORM_ANDROID,
        )

        info(self.event_id, f'PaymentTransaction created, id={tx.id}')
        return tx

    @staticmethod
    def payment_transaction_update(payment: PaymentTransaction, data: HandlerArgs):
        purchase = data.purchase
        payment.paid_until = data.purchase.expiry_date
        payment.external_payment_response = purchase.payload

        payment.save()

    @staticmethod
    def payment_transaction_refund(
        payment: PaymentTransaction, data: HandlerArgs, paid_until: datetime
    ):
        purchase = data.purchase
        payment.paid_until = paid_until

        payment.external_payment_response = purchase.payload
        payment.status = PaymentTransaction.STATUS_CANCELED

        payment.save()

    @abstractmethod
    def handle(self, data: HandlerArgs) -> ProcessingResult:
        pass


def subscription_comparator(sub1: Subscription, sub2: Subscription):
    """
    Compare subscription based on status and id.
    Status order:
        ACTIVE first
        IN_GRACE_PERIOD after
        EXPIRED last
    ID order:
        larger id first
    """

    def compare_ids(id1: int, id2: int):
        if id1 > id2:
            return -1

        return 1

    def compare_status(left: Subscription, right: Subscription, target_status: int):
        if left.status == right.status and left.status == target_status:
            return compare_ids(left.id, right.id)

        if left.status == target_status:
            return -1

        if right.status == target_status:
            return 1

        return 0

    status_order = [
        Subscription.STATUS_ACTIVE,
        Subscription.STATUS_GRACE_PERIOD,
        Subscription.STATUS_EXPIRED,
    ]
    for status in status_order:
        result = compare_status(sub1, sub2, status)

        if result != 0:
            return result

    return compare_ids(sub1.id, sub2.id)
