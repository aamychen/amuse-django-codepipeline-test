from django.db import transaction

from .abstract_handler import AbstractNotificationHandler
from .containers import HandlerArgs
from ..enums import ProcessingResult
from ..helpers import info


class DeferredNotificationHandler(AbstractNotificationHandler):
    """
    You can advance the next billing date for a subscriber by using
    Purchases.subscriptions:defer from the Google Play Developer API.
    During the deferral period, the user is subscribed to your content with full access
    but is not charged. The subscription renewal date is updated to reflect the new date.

    Billing can be deferred by as little as one day and by as long as one year per
    API call. To defer the billing even further, you can call the API again
    before the new billing date arrives.

    https://developer.android.com/google/play/billing/subscriptions#defer
    """

    @transaction.atomic
    def handle(self, data: HandlerArgs) -> ProcessingResult:
        purchase = data.purchase

        payment = self.get_payment_transaction(data)
        self.payment_transaction_update(payment, data)
        subscription = payment.subscription

        info(
            self.event_id,
            f'Subscription DEFERRED, id={subscription.id}, transaction_id={payment.id}',
        )

        return ProcessingResult.SUCCESS
