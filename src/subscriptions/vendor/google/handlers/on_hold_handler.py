from typing import Optional

from django.db import transaction

from payments.models import PaymentTransaction
from subscriptions.models import Subscription
from subscriptions.rules import Action, ChangeReason
from .abstract_handler import AbstractNotificationHandler
from .containers import HandlerArgs
from ..enums import ProcessingResult
from ..helpers import info


class OnHoldNotificationHandler(AbstractNotificationHandler):
    """
    Account hold is a subscription state that begins when a user's form of payment
    fails and any associated grace period has ended without payment resolution.
    When a subscription enters into account hold, you should block access to your
    content or service. The account hold period lasts for up to 30 days.

    https://developer.android.com/google/play/billing/subscriptions#account-hold
    """

    @transaction.atomic
    def handle(self, data: HandlerArgs):
        """
        Since amuse does not support ON_HOLD, subscription is EXPIRED
        """

        # NOTE: In PAUSED -> ON_HOLD flow, new orderId (non-paid) will be received.
        # However, we don't want to create new PaymentTransaction here. Why?
        # If we create new transaction, then we need to create new subscription (we
        # don't want to associate NON-PAID transaction with EXPIRED subscription.
        # Moreover we dont know if this transaction will be ever charged).
        # Let's ignore new transaction here, and we will create it when we receive
        # RECOVERED event.
        payment = self.get_payment_transaction(data, raise_exception=False)
        subscription = self.get_subscription(payment, data)

        if subscription.status == Subscription.STATUS_EXPIRED:
            info(self.event_id, f'Subscription already expired, id={subscription.id}')
            return ProcessingResult.SUCCESS

        Action.expire(
            subscription, data.purchase.expiry_date, ChangeReason.GOOGLE_ON_HOLD
        )

        info(
            self.event_id, f'Subscription EXPIRED due to ON_HOLD, id={subscription.id}'
        )
        return ProcessingResult.SUCCESS

    def get_subscription(
        self, payment: Optional[PaymentTransaction], data: HandlerArgs
    ):
        if payment is not None:
            return payment.subscription

        return self.get_handleable_subscription(data)
