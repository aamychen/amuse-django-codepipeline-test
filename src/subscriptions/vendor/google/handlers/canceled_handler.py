from datetime import datetime

from django.db import transaction
from django.utils.timezone import make_aware

from amuse.analytics import subscription_canceled
from subscriptions.models import Subscription
from subscriptions.rules import Action, ChangeReason, Rule
from .abstract_handler import AbstractNotificationHandler
from .containers import HandlerArgs
from ..enums import ProcessingResult
from ..errors import SubscriptionCannotCancel
from ..helpers import info


class CanceledNotificationHandler(AbstractNotificationHandler):
    """
    When you receive this notification, the subscription resource returned from the
    Google Play Developer API contains autoRenewing = false,
    and the expiryTimeMillis contains the date when the user should lose access to the
    subscription.

    If expiryTimeMillis is in the past, then the user loses entitlement immediately.
    Otherwise, the user should retain entitlement until it is expired.

    https://developer.android.com/google/play/billing/subscriptions#cancel
    """

    @transaction.atomic
    def handle(self, data: HandlerArgs) -> ProcessingResult:
        purchase = data.purchase

        payment = self.get_payment_transaction(data)
        subscription = payment.subscription

        paid_until = purchase.expiry_date
        expiry_in_the_past = paid_until < make_aware(datetime.utcnow())

        if subscription.status == Subscription.STATUS_EXPIRED and expiry_in_the_past:
            # Occurs if google subscription status is PAUSED and then user CANCELS the subscription.
            # NOTE: if google subscription status is PAUSED, then amuse status is EXPIRED
            info(
                self.event_id,
                f'Subscription CANNOT CANCEL. It is EXPIRED already, id={subscription.id}',
            )
            return ProcessingResult.SUCCESS

        if not Rule.can_cancel(subscription):
            raise SubscriptionCannotCancel(subscription.id, subscription.status)

        if expiry_in_the_past:
            # it's in the past -> EXPIRE the subscription immediately
            return self.cancel_immediately(paid_until, subscription, payment, data)

        return self.cancel(paid_until, subscription, payment, data)

    def cancel(self, paid_until, subscription, payment, data):
        Action.cancel(subscription, paid_until, ChangeReason.GOOGLE_CANCELED)
        self.payment_transaction_update(payment, data)
        info(self.event_id, f'Subscription CANCELED, id={subscription.id}')
        subscription_canceled(subscription)
        return ProcessingResult.SUCCESS

    def cancel_immediately(self, paid_until, subscription, payment, data):
        Action.expire(
            subscription, paid_until, ChangeReason.GOOGLE_CANCELED_IMMEDIATELY
        )
        self.payment_transaction_update(payment, data)
        subscription_canceled(subscription)
        info(self.event_id, f'Subscription CANCELED IMMEDIATELY, id={subscription.id}')
        return ProcessingResult.SUCCESS
