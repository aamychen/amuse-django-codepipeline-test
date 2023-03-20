from datetime import datetime
from typing import Optional

from django.db import transaction
from django.utils import timezone

from amuse.analytics import subscription_changed
from amuse.analytics import (
    subscription_new_intro_started,
    subscription_new_started,
    subscription_trial_started,
)
from amuse.platform import PlatformType
from payments.models import PaymentMethod, PaymentTransaction
from subscriptions.models import Subscription
from subscriptions.rules import Action, ChangeReason
from users.models import User
from .abstract_handler import AbstractNotificationHandler
from .containers import HandlerArgs
from ..enums import ProcessingResult
from ..errors import PaymentTransactionAlreadyExistsError
from ..helpers import info
from ..processors.subscription_creator import (
    SubscriptionCreator,
    SubscriptionCreatorArgs,
)


class PurchasedNotificationHandlerV2(AbstractNotificationHandler):
    def __init__(self, event_id: str, user: User):
        self.user = user

        super(PurchasedNotificationHandlerV2, self).__init__(event_id=event_id)

    @transaction.atomic
    def handle(self, data: HandlerArgs):
        if self.is_upgrade_flow(data):
            return Upgrade(self.event_id, self.user).handle(data)

        subscription = self.create_new_subscription(data)

        self.trigger_analytics(subscription, subscription.latest_payment())

        return ProcessingResult.SUCCESS

    def create_new_subscription(self, data: HandlerArgs):
        customer_payload = {
            'google_subscription_id': data.google_subscription_id,
            'purchase_token': data.purchase_token,
        }

        subscription = SubscriptionCreator().create_from_purchase_notification(
            self.event_id, self.user, customer_payload, purchase=data.purchase
        )

        return subscription

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

    @staticmethod
    def trigger_analytics(subscription, payment):
        subscription_started_functions = {
            PaymentTransaction.TYPE_FREE_TRIAL: subscription_trial_started,
            PaymentTransaction.TYPE_INTRODUCTORY_PAYMENT: subscription_new_intro_started,
        }
        subscription_started = subscription_started_functions.get(
            payment.type, subscription_new_started
        )

        subscription_started(
            subscription, PlatformType.ANDROID, None, None, payment.country.code
        )


class Upgrade(AbstractNotificationHandler):
    def __init__(self, event_id: str, user: User):
        self.user = user
        super(Upgrade, self).__init__(event_id=event_id)

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

        params = SubscriptionCreatorArgs(
            purchase_token=data.purchase_token,
            google_subscription_id=data.google_subscription_id,
            purchase=data.purchase,
            plan=plan,
            change_reason=ChangeReason.GOOGLE_UPGRADE_NEW_V2,
            is_renewal=True,
            is_upgrade=True,
            customer_payload=None,
        )
        subscription = SubscriptionCreator().create_from_google_webhook(
            self.event_id, self.user, params
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

        info(self.event_id, f'Subscription CREATED (UPGRADE) v2, id={subscription.id}')
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
            Action.expire(sub, valid_until, ChangeReason.GOOGLE_UPGRADE_EXPIRE_V2)
            info(self.event_id, f'Subscription EXPIRED (UPGRADE) v2, id={sub.id}')

        if subscriptions:
            return subscriptions[0]

        return None
