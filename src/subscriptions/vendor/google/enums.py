import enum


class AcknowledgementState(enum.IntEnum):
    """
    The acknowledgement state of the subscription product.
    Possible values are:
        0. Yet to be acknowledged
        1. Acknowledged

    https://developers.google.com/android-publisher/api-ref/rest/v3/purchases.subscriptions#resource:-subscriptionpurchase
    """

    TO_BE_ACKNOWLEDGED = 0
    ACKNOWLEDGED = 1


class CancelReason(enum.IntEnum):
    """
    The reason why a subscription was canceled or is not auto-renewing.
    Possible values are:
        0. User canceled the subscription
        1. Subscription was canceled by the system, for example because of a billing problem
        2. Subscription was replaced with a new subscription
        3. Subscription was canceled by the developer

    https://developers.google.com/android-publisher/api-ref/rest/v3/purchases.subscriptions#resource:-subscriptionpurchase
    """

    USER = 0
    SYSTEM = 1
    REPLACED_BY_NEW_SUBSCRIPTION = 2
    DEVELOPER = 3


class InAppProductType(enum.Enum):
    """
    The type of the product.

    Possible values are:
        managedUser - The default product type - one time purchase.
        subscription - In-app product with a recurring period.

    Note: in official documentation (see link below) there is an additional value: PURCHASE_TYPE_UNSPECIFIED.

    https://developers.google.com/android-publisher/api-ref/rest/v3/inappproducts#purchasetype
    """

    # The default product type - one time purchase.
    ONE_TIME = 'managedUser'

    # In-app product with a recurring period.
    SUBSCRIPTION = 'subscription'


class PaymentState(enum.IntEnum):
    """
    The payment state of the subscription.

    Possible values are:
        0. Payment pending
        1. Payment received
        2. Free trial
        3. Pending deferred upgrade/downgrade

    NOTE: Not present for canceled, expired subscriptions.

    https://developers.google.com/android-publisher/api-ref/rest/v3/purchases.subscriptions#resource:-subscriptionpurchase
    """

    PENDING = 0
    RECEIVED = 1
    FREE_TRIAL = 2
    DEFERRED = 3


class SubscriptionNotificationType(enum.IntEnum):
    """
    The notificationType for a subscription can have the following values:
        1. RECOVERED - A subscription was recovered from account hold.
        2. RENEWED - An active subscription was renewed.
        3. CANCELED - A subscription was either voluntarily or involuntarily cancelled. For voluntary cancellation, sent when the user cancels.
        4. PURCHASED - A new subscription was purchased.
        5. ON_HOLD - A subscription has entered account hold (if enabled).
        6. IN_GRACE_PERIOD - A subscription has entered grace period (if enabled).
        7. RESTARTED - User has reactivated their subscription from Play > Account > Subscriptions (requires opt-in for subscription restoration).
        8. PRICE_CHANGE_CONFIRMED - A subscription price change has successfully been confirmed by the user.
        9. DEFERRED - A subscription's recurrence time has been extended.
        10. PAUSED - A subscription has been paused.
        11. PAUSE_SCHEDULE_CHANGED - A subscription pause schedule has been changed.
        12. REVOKED - A subscription has been revoked from the user before the expiration time.
        13. EXPIRED - A subscription has expired.

    https://developer.android.com/google/play/billing/rtdn-reference#sub
    """

    RECOVERED = 1
    RENEWED = 2
    CANCELED = 3
    PURCHASED = 4
    ON_HOLD = 5
    IN_GRACE_PERIOD = 6
    RESTARTED = 7
    PRICE_CHANGE_CONFIRMED = 8
    DEFERRED = 9
    PAUSED = 10
    PAUSE_SCHEDULE_CHANGED = 11
    REVOKED = 12
    EXPIRED = 13

    UNKNOWN = -1

    def __missing__(self, key):
        return self.UNKNOWN


class SubscriptionPurchaseType(enum.IntEnum):
    """
    The type of purchase of the subscription.
    This field is only set if this purchase was not made using the standard in-app billing flow.

    Possible values are:
        0. Test (i.e. purchased from a license testing account)
        1. Promo (i.e. purchased using a promo code)

    https://developers.google.com/android-publisher/api-ref/rest/v3/purchases.subscriptions#SubscriptionPurchase
    """

    TEST = 0
    PROMO = 1


class ProcessingResult(enum.IntEnum):
    """
    Enumerated result

    Possible values are:
        0. FAIL - NotificationProcessor fail to process notification
        1. SUCCESS - NotificationProcessor manage to process notification successfully

    """

    FAIL = 0
    SUCCESS = 1
