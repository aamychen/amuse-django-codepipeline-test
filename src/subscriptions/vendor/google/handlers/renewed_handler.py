from datetime import datetime

from django.db import transaction
from django.utils import timezone

from amuse.analytics import subscription_changed, subscription_successful_renewal
from payments.models import PaymentMethod
from subscriptions.models import Subscription
from subscriptions.rules import Action, ChangeReason
from .abstract_handler import AbstractNotificationHandler
from .containers import HandlerArgs
from ..enums import ProcessingResult
from ..errors import PaymentTransactionAlreadyExistsError
from ..google_play_api import GooglePlayAPI
from ..helpers import info
from ..processors.subscription_creator import (
    SubscriptionCreatorArgs,
    SubscriptionCreator,
)


class RenewedNotificationHandler(AbstractNotificationHandler):
    """
    Handler for RENEWED (an active subscription was renewed) notification type.

    Handler:
        - renews existing subscription, or
        - downgrade (DEFERRED) existing sub to the sub with a lower price
        - creates new one if subscription is missing (after PAUSED/ON_HOLD google states)
    """

    @transaction.atomic
    def handle(self, data: HandlerArgs):
        if self.is_downgrade_flow(data):
            return Downgrade(self.event_id).handle(data)

        subscription = self.get_active_subscription_by_token(data.purchase_token)
        if subscription is None:
            # Active subscription does not exist in amuse DB, although google sub exists.
            # Since Amuse does not support PAUSED or ON_HOLD status,
            # probably there is EXPIRED amuse sub. Since the original sub is expired, we need to create new sub.
            return self.new_subscription(data)

        if data.purchase.expiry_date < timezone.now():
            # Sometimes, RENEWED is received for expired/canceled subscription.
            # Don't have a valid explanation!? ¯\_(ツ)_/¯
            return self.expire_subscription(subscription, data)

        # there is 1 active subscription -> regular flow
        return self.renew_subscription(subscription, data)

    def expire_subscription(self, subscription: Subscription, data: HandlerArgs):
        Action.expire(
            subscription, data.purchase.expiry_date, ChangeReason.RENEW_IN_PAST
        )
        info(self.event_id, f'Subscription EXPIRED, id={subscription.id}')
        return ProcessingResult.SUCCESS

    def new_subscription(self, data: HandlerArgs):
        payment = self.get_payment_transaction(data, raise_exception=False)

        if payment is not None:
            # PaymentTransaction must not exist in this moment
            raise PaymentTransactionAlreadyExistsError(data.purchase.order_id)

        payment_method = self.get_payment_method(data)
        plan = self.get_plan(data)

        params = SubscriptionCreatorArgs(
            purchase_token=data.purchase_token,
            google_subscription_id=data.google_subscription_id,
            purchase=data.purchase,
            plan=plan,
            change_reason=ChangeReason.GOOGLE_RENEW_NEW,
            is_renewal=True,
            is_upgrade=False,
            customer_payload=None,
        )
        subscription = SubscriptionCreator().create_from_google_webhook(
            self.event_id, payment_method.user, params
        )

        subscription_successful_renewal(
            subscription, data.purchase.price_amount, data.purchase.country_code
        )
        info(self.event_id, f'Subscription CREATED, id={subscription.id}')
        return ProcessingResult.SUCCESS

    def renew_subscription(self, active_subscription: Subscription, data: HandlerArgs):
        Action.activate(active_subscription, ChangeReason.GOOGLE_RENEW)

        payment = self.get_payment_transaction(data, raise_exception=False)
        if payment is None:
            self.payment_transaction_new(active_subscription, data)
        else:
            # rarely, google enters retard-mode and send multiple RENEW message with
            # same content (but different messageId)
            self.payment_transaction_update(payment, data)

        subscription_successful_renewal(
            active_subscription, data.purchase.price_amount, data.purchase.country_code
        )
        info(self.event_id, f'Subscription RENEWED, id={active_subscription.id}')
        return ProcessingResult.SUCCESS

    @staticmethod
    def is_downgrade_flow(data: HandlerArgs):
        """
        Downgrade flow represents first RENEWAL after downgrade.
        """
        if data.purchase.linked_purchase_token is None:
            return False

        return not PaymentMethod.objects.filter(
            external_recurring_id=data.purchase_token
        ).exists()


class Downgrade(AbstractNotificationHandler):
    def handle(self, data: HandlerArgs):
        """
        Change active_subscription status to EXPIRED.
        Create new subscription with new plan and payment method.


        https://developer.android.com/google/play/billing/subscriptions#upgrade-downgrade
        """
        today = timezone.now().today()

        previous_subscription = self.downgrade(data, today)

        plan = self.get_plan(data)

        payment = self.get_payment_transaction(data, raise_exception=False)
        if payment is not None:
            raise PaymentTransactionAlreadyExistsError(data.purchase.order_id)

        previous_payment_method = PaymentMethod.objects.filter(
            external_recurring_id=data.purchase.linked_purchase_token
        ).first()

        params = SubscriptionCreatorArgs(
            purchase_token=data.purchase_token,
            google_subscription_id=data.google_subscription_id,
            purchase=data.purchase,
            plan=plan,
            change_reason=ChangeReason.GOOGLE_DOWNGRADE_NEW,
            is_renewal=True,
            is_upgrade=False,
            customer_payload=None,
        )
        subscription = SubscriptionCreator().create_from_google_webhook(
            self.event_id, previous_payment_method.user, params
        )

        GooglePlayAPI().acknowledge(
            self.event_id, data.google_subscription_id, data.purchase_token
        )

        if previous_subscription:
            subscription_changed(
                subscription,
                previous_subscription.plan,
                plan,
                None,
                None,
                data.purchase.country_code,
            )
        subscription_successful_renewal(
            subscription, data.purchase.price_amount, data.purchase.country_code
        )

        info(self.event_id, f'Subscription CREATED (DOWNGRADE), id={subscription.id}')
        return ProcessingResult.SUCCESS

    def downgrade(self, data: HandlerArgs, valid_until: datetime):
        """
        Expire all previous subscriptions.
        """
        subscriptions = list(
            Subscription.objects.filter(
                payment_method__external_recurring_id=data.purchase.linked_purchase_token,
                provider=Subscription.PROVIDER_GOOGLE,
                status__in=[
                    Subscription.STATUS_ACTIVE,
                    Subscription.STATUS_GRACE_PERIOD,
                ],
            )
        )

        # NOTE: there should be only 1 subscription in the list
        # SANITY CHECK: EXPIRE full list
        for sub in subscriptions:
            Action.expire(sub, valid_until, ChangeReason.GOOGLE_DOWNGRADE_EXPIRE)
            info(self.event_id, f'Subscription EXPIRED (DOWNGRADE), id={sub.id}')

        if subscriptions:
            return subscriptions[0]

        return None
