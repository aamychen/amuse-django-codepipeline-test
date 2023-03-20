from django.db import transaction

from amuse.analytics import subscription_renewal_error
from subscriptions.models import Subscription
from subscriptions.rules import Action, ChangeReason
from .abstract_handler import AbstractNotificationHandler
from .containers import HandlerArgs
from ..enums import ProcessingResult
from ..errors import SubscriptionActiveNotFoundPurchaseTokenError
from ..helpers import info


class GracePeriodNotificationHandler(AbstractNotificationHandler):
    """
    If grace period is enabled, subscriptions enter grace period if there are
    payment issues at the end of a billing cycle. During this time, the user should
    still have access to the subscription while Google Play tries to renew
    the subscription.

    https://developer.android.com/google/play/billing/subscriptions#grace
    """

    @transaction.atomic
    def handle(self, data: HandlerArgs):
        subscription = self.get_active_subscription_by_token(data.purchase_token)

        if subscription is None:
            raise SubscriptionActiveNotFoundPurchaseTokenError(data.purchase_token)

        purchase = data.purchase

        previous_state = subscription.status

        Action.enter_grace_period(
            subscription, purchase.expiry_date, ChangeReason.GOOGLE_GRACE_PERIOD
        )

        if previous_state == Subscription.STATUS_ACTIVE:
            subscription_renewal_error(subscription, data.purchase.country_code)

        info(self.event_id, f'Subscription IN_GRACE_PERIOD, id={subscription.id}')
        return ProcessingResult.SUCCESS
