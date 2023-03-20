from django.db import transaction
from subscriptions.models import Subscription
from subscriptions.rules import Action, ChangeReason, Rule

from .abstract_handler import AbstractNotificationHandler
from .containers import HandlerArgs
from ..enums import ProcessingResult
from ..errors import SubscriptionCannotExpire
from ..helpers import info, warning


class PausedNotificationHandler(AbstractNotificationHandler):
    """
    A SUBSCRIPTION_PAUSED Real-time developer notification is sent when the pause goes
    into effect. At this time, the user should lose access to their subscription,
    and the subscription resource contains
        autoRenewing = true,
        and a paymentState = 0 (pending),
        a future value for autoResumeTimeMillis,
        and a past value for expiryTimeMillis.

    https://developer.android.com/google/play/billing/subscriptions#pause
    """

    @transaction.atomic
    def handle(self, data: HandlerArgs):
        """
        Since amuse does not support PAUSE, subscription is EXPIRED
        """
        payment = self.get_payment_transaction(data)

        subscription = payment.subscription
        purchase = data.purchase

        if subscription.status == Subscription.STATUS_EXPIRED:
            info(self.event_id, f'Subscription already expired, id={subscription.id}')
            return ProcessingResult.SUCCESS

        if not Rule.can_expire(subscription):
            raise SubscriptionCannotExpire(subscription.id, subscription.status)

        Action.expire(subscription, purchase.expiry_date, ChangeReason.GOOGLE_PAUSED)

        info(self.event_id, f'Subscription EXPIRED due to PAUSE, id={subscription.id}')
        return ProcessingResult.SUCCESS
