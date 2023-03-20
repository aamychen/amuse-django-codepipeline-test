from datetime import datetime
from typing import Optional

from django.db import transaction
from django.utils import timezone

from amuse.analytics import subscription_changed
from payments.models import PaymentMethod
from subscriptions.models import Subscription
from subscriptions.rules import Action, ChangeReason
from .abstract_handler import AbstractNotificationHandler
from .containers import HandlerArgs
from ..enums import ProcessingResult
from ..errors import PaymentTransactionAlreadyExistsError
from ..helpers import info
from ..processors.subscription_creator import (
    SubscriptionCreator,
    SubscriptionCreatorArgs,
)


class PurchasedNotificationHandlerV1(AbstractNotificationHandler):
    @transaction.atomic
    def handle(self, data: HandlerArgs):
        if self.is_upgrade_flow(data):
            return Upgrade(self.event_id).handle(data)

        # If not upgrade, then IGNORE.
        # Subscription is created via POST /api/subscriptions/google endpoint
        # Since we do not know owner (user) of the subscription, it cannot be created here.
        info(self.event_id, f'Not UPGRADE flow. Ignore.')
        return ProcessingResult.SUCCESS

    @staticmethod
    def is_upgrade_flow(data: HandlerArgs):
        """
        Upgrade flow represents first RENEWAL after upgrade.
        """
        if data.purchase.linked_purchase_token is None:
            return False

        payment_method = PaymentMethod.objects.filter(
            external_recurring_id=data.purchase_token
        ).first()

        return payment_method is None


class Upgrade(AbstractNotificationHandler):
    def handle(self, data: HandlerArgs):
        """
        Change active_subscription status to EXPIRED.
        Create new subscription with new plan and payment method.

        https://developer.android.com/google/play/billing/subscriptions#upgrade-downgrade
        """
        today = timezone.now().today()

        previous_subscription = self.expire_previous_subscriptions(data, today)

        plan = self.get_plan(data)

        payment = self.get_payment_transaction(data, raise_exception=False)
        if payment is not None:
            raise PaymentTransactionAlreadyExistsError(data.purchase.order_id)

        previous_payment_method = PaymentMethod.objects.filter(
            external_recurring_id=data.purchase.linked_purchase_token
        ).first()

        user = previous_payment_method.user

        params = SubscriptionCreatorArgs(
            purchase_token=data.purchase_token,
            google_subscription_id=data.google_subscription_id,
            purchase=data.purchase,
            plan=plan,
            change_reason=ChangeReason.GOOGLE_UPGRADE_NEW,
            is_renewal=True,
            is_upgrade=True,
            customer_payload=None,
        )
        subscription = SubscriptionCreator().create_from_google_webhook(
            self.event_id, user, params
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

        info(self.event_id, f'Subscription CREATED (UPGRADE), id={subscription.id}')
        return ProcessingResult.SUCCESS

    def expire_previous_subscriptions(
        self, data: HandlerArgs, valid_until: datetime
    ) -> Optional[Subscription]:
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
            Action.expire(sub, valid_until, ChangeReason.GOOGLE_UPGRADE_EXPIRE)
            info(self.event_id, f'Subscription EXPIRED (UPGRADE), id={sub.id}')

        if subscriptions:
            return subscriptions[0]

        return None
