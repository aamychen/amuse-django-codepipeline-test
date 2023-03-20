from django.db import transaction

from subscriptions.rules import Action, ChangeReason, Rule
from .abstract_handler import AbstractNotificationHandler
from .containers import HandlerArgs
from ..enums import ProcessingResult
from ..errors import SubscriptionCannotResubscribeError
from ..helpers import info


class RestartedNotificationHandler(AbstractNotificationHandler):
    """
    A cancelled subscription remains visible in the Play Store app until its expiration
    date. A user can restore a cancelled subscription before it expires by clicking
    Resubscribe (previously Restore) in the Subscriptions section in the
    Google Play Store app.

    Once received, record that the subscription is now set to renew, and stop
    displaying restoration messaging in your app.

    https://developer.android.com/google/play/billing/subscriptions#restore
    """

    @transaction.atomic
    def handle(self, data: HandlerArgs):
        payment = self.get_payment_transaction(data)
        subscription = payment.subscription

        if not Rule.can_resubscribe(subscription):
            raise SubscriptionCannotResubscribeError(
                subscription.id, subscription.status
            )

        Action.resubscribe(subscription, ChangeReason.GOOGLE_RESTARTED)
        self.payment_transaction_update(payment, data)

        info(self.event_id, f'Subscription RESTARTED, id={subscription.id}')
        return ProcessingResult.SUCCESS
