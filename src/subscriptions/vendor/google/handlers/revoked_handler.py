from django.db import transaction

from payments.models import PaymentTransaction
from subscriptions.models import Subscription
from subscriptions.rules import Action, ChangeReason, Rule
from .abstract_handler import AbstractNotificationHandler
from .containers import HandlerArgs
from ..enums import ProcessingResult
from ..helpers import info


class RevokedNotificationHandler(AbstractNotificationHandler):
    """
    Handler for REVOKE notification type.
    A subscription has been revoked from the user before the expiration time.
    """

    @transaction.atomic
    def handle(self, data: HandlerArgs):
        subscription = self.get_handleable_subscription(data)
        payment = self.get_payment_transaction(data)

        expiry_date = self.get_expiry_date(subscription)

        reason = ChangeReason.GOOGLE_REVOKED
        if not Rule.can_expire(subscription):
            reason = ChangeReason.GOOGLE_REVOKED_EXPIRED_SUB

        Action.expire(subscription, expiry_date, reason)
        self.payment_transaction_refund(payment, data, expiry_date)

        info(
            self.event_id,
            f'Subscription REVOKED, id={subscription.id}, reason={str(reason)}',
        )

        return ProcessingResult.SUCCESS

    @staticmethod
    def get_expiry_date(subscription: Subscription):
        """
        This function will determine new expiration date for subscription.
        It will use database values to find the expiration date.
        Expiration date is either paid_until from penultimate transaction, or valid_from
        from subscription.

        Alternative way to find expiration date is to take it directly from notification
        object (e.g. data.purchase.expiry_date). However, I have noticed that Google for
        refund scenario sends two notifications: REVOKE + EXPIRED. Expiry date is
        received with both notification payloads, however, expiry date values
        are different in REVOKE and EXPIRED payloads ¯\_(ツ)_/¯.
        """
        payments = list(
            PaymentTransaction.objects.filter(
                subscription_id=subscription.id,
                status__in=[
                    PaymentTransaction.STATUS_APPROVED,
                    PaymentTransaction.STATUS_CANCELED,
                ],
            ).order_by('-id')
        )

        if len(payments) > 1:
            # last transaction is refunded.
            # because of that, subscription should be valid to the paid_until of second
            # last subscription (in other words: second transaction in the list)
            return payments[1].paid_until

        # if there is only one transaction (or zero - which should not be possible),
        # subscription.valid_until is equal to subscription.valid_from
        return subscription.valid_from
