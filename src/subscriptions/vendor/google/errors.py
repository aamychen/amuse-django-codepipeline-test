"""
Google Notification related errors.

There are three levels:
 - BaseNotificationError - all other errors are inherited from this one
 - NotificationError and NotificationWarning - indicates what type of log message should be written (log.error or log.warning)
 - Concrete Error Types (e.g. MissingSubscriptionPlanError) - error message carriers.
"""


# Level 1


class BaseNotificationError(Exception):
    """
    Error intentionally raised by the notification handlers.
    Level: 1
    """

    pass


# Level 2


class NotificationError(BaseNotificationError):
    """
    log.Error should be written when this type of error is raised
    Level: 2
    """

    pass


class NotificationWarning(BaseNotificationError):
    """
    log.Warning should be written when this type of error is raised
    Level: 2
    """

    pass


# Level 3


class PurchaseTokenAlreadyUsedError(NotificationWarning):
    """
    Indicates that PaymentMethod is already create for the specified purchase_token.
    Level: 3
    """

    def __init__(self, *args, **kwargs):
        super(PurchaseTokenAlreadyUsedError, self).__init__(
            f'Already used purchase_token.', *args
        )


class PaymentTransactionNotFoundError(NotificationWarning):
    """
    Indicates that specified PaymentTransaction is missing in db
    Level: 3
    """

    def __init__(self, external_transaction_id: str, *args, **kwargs):
        super(PaymentTransactionNotFoundError, self).__init__(
            f'PaymentTransaction missing, external_transaction_id={external_transaction_id}',
            *args,
        )


class SubscriptionPlanNotFoundError(NotificationWarning):
    """
    Indicates that specified SubscriptionPlan is missing in db
    Level: 3
    """

    def __init__(self, google_product_id: str, *args, **kwargs):
        super(SubscriptionPlanNotFoundError, self).__init__(
            f'SubscriptionPlan missing, google_product_id={google_product_id}', *args
        )


class SubscriptionsMultipleActiveError(NotificationError):
    """
    Indicates that there are multiple active subscriptions for specified user.
    1 or 0 active subscriptions allowed per user.
    Level: 3
    """

    def __init__(self, user_id: int, subs: list, *args, **kwargs):
        super(SubscriptionsMultipleActiveError, self).__init__(
            f'Multiple active subscriptions found, user_id={user_id}, subs={subs}',
            *args,
        )


class SubscriptionsMultipleActivePurchaseTokenError(NotificationError):
    """
    Indicates that there are multiple active subscriptions for specified purchase token.
    1 or 0 active subscriptions allowed per user.
    Level: 3
    """

    def __init__(self, purchase_token: str, subs: list, *args, **kwargs):
        super(SubscriptionsMultipleActivePurchaseTokenError, self).__init__(
            f'Multiple active subscriptions found, purchase_token={purchase_token}, subs={subs}',
            *args,
        )


class SubscriptionActiveNotFoundPurchaseTokenError(NotificationError):
    """
    Indicates that there is no active subscription for specified purchaseToken, although there should be 1 active subscription.
    Level: 3
    """

    def __init__(self, purchase_token: str, *args, **kwargs):
        super(SubscriptionActiveNotFoundPurchaseTokenError, self).__init__(
            f'Active Subscription not found, purchase_token={purchase_token}', *args
        )


class SubscriptionNotFoundError(NotificationError):
    """
    Indicates that there is no subscription for specified user, although there should be at least active|grace|expired subscription.
    Level: 3
    """

    def __init__(self, purchase_token: str, *args, **kwargs):
        super(SubscriptionNotFoundError, self).__init__(
            f'Subscription not found, purchase_token={purchase_token}', *args
        )


class SubscriptionCannotCancel(NotificationError):
    """
    Indicates that Subscription status cannot be changed to CANCELED.
    Level: 3
    """

    def __init__(self, subscription_id: int, status: int, *args, **kwargs):
        super(SubscriptionCannotCancel, self).__init__(
            f'Subscription cannot cancel, id={subscription_id}, status={status}', *args
        )


class SubscriptionCannotExpire(NotificationError):
    """
    Indicates that Subscription status cannot be changed to EXPIRED.
    Level: 3
    """

    def __init__(self, subscription_id: int, status: int, *args, **kwargs):
        super(SubscriptionCannotExpire, self).__init__(
            f'Subscription cannot expire, id={subscription_id}, status={status}', *args
        )


class SubscriptionCannotResubscribeError(NotificationError):
    """
    Indicates that Subscription status cannot be changed to ACTIVE.
    Level: 3
    """

    def __init__(self, subscription_id: int, status: int, *args, **kwargs):
        super(SubscriptionCannotResubscribeError, self).__init__(
            f'Subscription cannot resubscribe, id={subscription_id}, status={status}',
            *args,
        )


class PaymentMethodNotFoundError(NotificationError):
    """
    Indicates that PaymentMethod is missing in db for specified purchase_token (external_recurring_id).
    Level: 3
    """

    def __init__(self, external_recurring_id: str, *args, **kwargs):
        super(PaymentMethodNotFoundError, self).__init__(
            f'PaymentMethod not found, external_recurring_id={external_recurring_id}',
            *args,
        )


class PaymentTransactionAlreadyExistsError(NotificationError):
    """
    Indicates that PaymentTransaction already exists, although it should not exists.
    Level: 3
    """

    def __init__(self, external_transaction_id: str, *args, **kwargs):
        super(PaymentTransactionAlreadyExistsError, self).__init__(
            f'PaymentTransaction already exists, external_transaction_id={external_transaction_id}',
            *args,
        )


class InvalidPurchaseTokenError(NotificationError):
    """
    Indicates that provided purchase_token is not valid.
    Level: 3
    """

    def __init__(
        self, google_subscription_id: str, purchase_token: str, *args, **kwargs
    ):
        super(InvalidPurchaseTokenError, self).__init__(
            f'Invalid purchase_token={purchase_token}, google_subscription_id={google_subscription_id}',
            *args,
        )


class UserNotEligibleForFreeTrial(NotificationError):
    """
    Indicates that user is not eligible for free_trial subscription.
    Level: 3
    """

    def __init__(self, user_id: str, *args, **kwargs):
        super(UserNotEligibleForFreeTrial, self).__init__(
            f'User id={user_id} is not eligible for free_trial.', *args
        )
