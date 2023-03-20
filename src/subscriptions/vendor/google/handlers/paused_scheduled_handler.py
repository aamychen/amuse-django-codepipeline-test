from django.db import transaction

from subscriptions.rules import Action, ChangeReason, Rule
from subscriptions.models import Subscription
from .abstract_handler import AbstractNotificationHandler
from .containers import HandlerArgs
from ..enums import ProcessingResult
from ..errors import SubscriptionCannotCancel
from ..helpers import info
from ..purchase_subscription import PurchaseSubscription


class PausedScheduledNotificationHandler(AbstractNotificationHandler):
    """
    You can prevent voluntary churn by enabling users to pause their subscription.
    When you enable the pause feature, users can choose to pause their subscription
    for a period of time between one week and three months, depending on the
    recurring period. Once enabled, the pause option surfaces both in the subscriptions
    center and in the cancel flow. Note that annual subscriptions cannot be paused,
    and the pause limits of one week and three months are subject to change at any time.

    A subscription pause takes effect only after the current billing period ends.
    While the subscription is paused, the user doesn't have access to the subscription.
    At the end of the pause period, the subscription resumes, and Google attempts
    to renew the subscription. If the resume is successful, the subscription becomes
    active again. If the resume fails due to a payment issue, the user enters
    the account hold state, as shown in figure 1:

    A SUBSCRIPTION_PAUSE_SCHEDULE_CHANGED Real-time developer notification is sent when
    your user initiates a pause of their subscription. At this time, the user should
    keep access to their subscription, and the subscription resource contains
        autoRenewing = true,
        paymentState = 1 (Payment Received),
        and future values for expiryTimeMillis and autoResumeTimeMillis.

    https://developer.android.com/google/play/billing/subscriptions#pause
    """

    @transaction.atomic
    def handle(self, data: HandlerArgs) -> ProcessingResult:
        """
        Since AMUSE does not support PAUSE, subscription is CANCELED.
        """
        purchase = data.purchase

        payment = self.get_payment_transaction(data)
        subscription = payment.subscription

        if purchase.auto_resume_time_millis is None:
            return self.resume(subscription)

        return self.cancel(subscription, purchase)

    def resume(self, subscription: Subscription):
        Action.activate(subscription, ChangeReason.GOOGLE_PAUSE_SCHEDULE_RESUMED)
        info(self.event_id, f'Subscription PAUSE RESUMED, id={subscription.id}')
        return ProcessingResult.SUCCESS

    def cancel(self, subscription: Subscription, purchase: PurchaseSubscription):
        if not Rule.can_cancel(subscription):
            raise SubscriptionCannotCancel(subscription.id, subscription.status)

        paid_until = purchase.expiry_date

        Action.cancel(subscription, paid_until, ChangeReason.GOOGLE_PAUSE_SCHEDULED)

        info(self.event_id, f'Subscription PAUSE SCHEDULED, id={subscription.id}')
        return ProcessingResult.SUCCESS
