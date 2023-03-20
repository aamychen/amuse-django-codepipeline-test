from datetime import datetime
from enum import IntEnum
from typing import Optional

from django.utils import timezone

from payments.models import PaymentMethod
from subscriptions.models import Subscription, SubscriptionPlan


class ChangeReason(IntEnum):
    """
    Reason for altering the subscription.
    This value should be used whenever subscription is modified in any way.
    It is stored to subscriptions_historicalsubscription.history_change_reason.
    """

    GOOGLE_EXPIRED = 1
    GOOGLE_CANCELED = 2
    GOOGLE_CANCELED_IMMEDIATELY = 3
    GOOGLE_RENEW = 4
    GOOGLE_RENEW_NEW = 5
    GOOGLE_RESTARTED = 6
    GOOGLE_GRACE_PERIOD = 7
    GOOGLE_PAUSE_SCHEDULED = 8
    GOOGLE_PAUSE_SCHEDULE_RESUMED = 9
    GOOGLE_RECOVERED = 10
    GOOGLE_PAUSED = 11
    GOOGLE_ON_HOLD = 12
    RENEW_IN_PAST = 13
    GOOGLE_DOWNGRADE_EXPIRE = 14
    GOOGLE_DOWNGRADE_NEW = 15
    GOOGLE_UPGRADE_EXPIRE = 16
    GOOGLE_UPGRADE_NEW = 17
    GOOGLE_REVOKED = 18
    GOOGLE_REVOKED_EXPIRED_SUB = 19
    GOOGLE_EXPIRED_UPDATE_DATE = 20
    GOOGLE_NEW = 21
    GOOGLE_ADMIN_NEW = 22
    GOOGLE_PURCHASED = 23
    GOOGLE_UPGRADE_NEW_V2 = 24
    GOOGLE_UPGRADE_EXPIRE_V2 = 25

    APPLE_CANCELED = 100
    APPLE_INTERACTIVE_RENEWAL = 101
    APPLE_DID_CHANGE_RENEWAL_STATUS = 102

    ADYEN_CANCELED = 200

    def __str__(self):
        return str(self.name)


class Action(object):
    """
    Collection of pure methods for subscription manipulation.
    """

    @staticmethod
    def create(
        payment_method: PaymentMethod,
        plan: SubscriptionPlan,
        provider: int,
        change_reason: ChangeReason,
        free_trial_from: Optional[datetime] = None,
        free_trial_until: Optional[datetime] = None,
        valid_until: Optional[datetime] = None,
    ):
        subscription = Subscription(
            payment_method=payment_method,
            plan=plan,
            provider=provider,
            status=Subscription.STATUS_ACTIVE,
            user=payment_method.user,
            valid_from=timezone.now().date(),
            valid_until=valid_until,
            free_trial_from=free_trial_from,
            free_trial_until=free_trial_until,
        )
        subscription._change_reason = change_reason
        subscription.save()
        return subscription

    @staticmethod
    def activate(subscription: Subscription, change_reason: ChangeReason):
        """
        Change status to ACTIVE and set valid_until and grace_period_until to None.
        """
        subscription.status = Subscription.STATUS_ACTIVE
        subscription.valid_until = None
        subscription.grace_period_until = None
        subscription._change_reason = str(change_reason)
        subscription.save()

    @staticmethod
    def enter_grace_period(
        subscription: Subscription,
        grace_period_until: datetime,
        change_reason: ChangeReason,
    ):
        """
        Change status to GRACE_PERIOD and set valid_until to None and set grace_period_until to provided value.
        """
        subscription.status = Subscription.STATUS_GRACE_PERIOD
        subscription.valid_until = None
        subscription.grace_period_until = grace_period_until
        subscription._change_reason = str(change_reason)
        subscription.save()

    @staticmethod
    def cancel(
        subscription: Subscription, valid_until: datetime, change_reason: ChangeReason
    ):
        """
        Change status to ACTIVE and set valid_until to actual value and and set grace_period_until to None.
        """
        subscription.status = Subscription.STATUS_ACTIVE
        subscription.valid_until = valid_until
        subscription.grace_period_until = None
        subscription._change_reason = str(change_reason)
        subscription.save()

    @staticmethod
    def expire(
        subscription: Subscription, valid_until: datetime, change_reason: ChangeReason
    ):
        """
        Change status of subscription to EXPIRED.
        """
        subscription.status = Subscription.STATUS_EXPIRED
        subscription.valid_until = valid_until
        subscription.grace_period_until = None

        subscription._change_reason = str(change_reason)
        subscription.save()

    @staticmethod
    def resubscribe(subscription: Subscription, change_reason: ChangeReason):
        """
        Wrapper for activate().
        """
        Action.activate(subscription, change_reason)


class Rule(object):
    """
    Collection of pure boolean methods for subscription inspection.
    """

    @staticmethod
    def can_activate(subscription):
        """
        Returns True if subscription can be activated.
        """
        if subscription is None:
            return False

        if subscription.status in [
            Subscription.STATUS_CREATED,
            Subscription.STATUS_ACTIVE,
            Subscription.STATUS_GRACE_PERIOD,
        ]:
            return True

        return False

    @staticmethod
    def can_cancel(subscription: Subscription):
        """Returns True if subscription can be canceled."""
        if subscription.status not in [
            Subscription.STATUS_ACTIVE,
            Subscription.STATUS_GRACE_PERIOD,
        ]:
            return False

        if subscription.valid_until is None:
            return True

        return False

    @staticmethod
    def can_expire(subscription: Subscription):
        """Returns True if subscription status can be changed to EXPIRED."""
        if subscription is None:
            return False

        if subscription.status not in [
            Subscription.STATUS_ACTIVE,
            Subscription.STATUS_GRACE_PERIOD,
        ]:
            return False

        return True

    @staticmethod
    def can_resubscribe(subscription: Subscription):
        """Returns True if subscription can be ACTIVATED after it is CANCELED."""
        return Rule.can_activate(subscription)
