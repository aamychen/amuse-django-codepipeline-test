from django.db import transaction

from payments.models import PaymentTransaction
from subscriptions.models import Subscription
from subscriptions.rules import Action, ChangeReason, Rule
from .abstract_handler import AbstractNotificationHandler
from .containers import HandlerArgs
from ..enums import ProcessingResult
from ..errors import SubscriptionCannotExpire
from ..helpers import info


class ExpiredNotificationHandler(AbstractNotificationHandler):
    """
    Handles subscription expiration

    https://developer.android.com/google/play/billing/subscriptions#expirations
    """

    @transaction.atomic
    def handle(self, data: HandlerArgs):
        payment = self.get_payment_transaction(data, raise_exception=False)

        if payment is None:
            # Edge case. In production it should be hard to reproduce. But can be easily
            # reproduced in test environment where renewal period is very short (order
            # of MINUTES). How to reproduce: brake communication between amuse-django
            # api and google notifications 1 renewal period before it expires.
            payment = self.recover_payment(data)

        subscription = payment.subscription
        purchase = data.purchase

        if subscription.status == Subscription.STATUS_EXPIRED:
            # sometimes google sends EXPIRED more than once,
            # usually to update expiry date
            return self.update_expired_subscription(data, subscription, payment)

        if not Rule.can_expire(subscription):
            raise SubscriptionCannotExpire(subscription.id, subscription.status)

        Action.expire(subscription, purchase.expiry_date, ChangeReason.GOOGLE_EXPIRED)

        info(self.event_id, f'Subscription EXPIRED, id={subscription.id}')
        return ProcessingResult.SUCCESS

    def recover_payment(self, data: HandlerArgs) -> PaymentTransaction:
        subscription = self.get_handleable_subscription(data)

        return self.payment_transaction_new(subscription, data)

    def update_expired_subscription(
        self, data: HandlerArgs, subscription: Subscription, payment: PaymentTransaction
    ):
        info(
            self.event_id,
            f'Subscription already expired, id={subscription.id}. '
            f'Updated expiry_date={data.purchase.expiry_date}',
        )

        self.payment_transaction_update(payment, data)
        Action.expire(
            subscription,
            data.purchase.expiry_date,
            ChangeReason.GOOGLE_EXPIRED_UPDATE_DATE,
        )

        return ProcessingResult.SUCCESS
