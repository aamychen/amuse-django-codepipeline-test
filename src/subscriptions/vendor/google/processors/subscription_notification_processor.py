from subscriptions.vendor.google.enums import SubscriptionNotificationType
from subscriptions.vendor.google import GooglePlayAPI, info

from .abstract_notification_processor import AbstractNotificationProcessor
from ..enums import ProcessingResult
from ..errors import NotificationError, NotificationWarning
from ..helpers import error, warning
from ..handlers import (
    HandlerArgs,
    CanceledNotificationHandler,
    DeferredNotificationHandler,
    ExpiredNotificationHandler,
    GracePeriodNotificationHandler,
    IgnoreNotificationHandler,
    OnHoldNotificationHandler,
    PausedNotificationHandler,
    PausedScheduledNotificationHandler,
    PurchasedNotificationHandler,
    RecoveredNotificationHandler,
    RenewedNotificationHandler,
    RevokedNotificationHandler,
    RestartedNotificationHandler,
    UnknownNotificationHandler,
)
from ..purchase_subscription import PurchaseSubscription

_handlers = {
    SubscriptionNotificationType.RECOVERED: RecoveredNotificationHandler,
    SubscriptionNotificationType.RENEWED: RenewedNotificationHandler,
    SubscriptionNotificationType.CANCELED: CanceledNotificationHandler,
    SubscriptionNotificationType.PURCHASED: PurchasedNotificationHandler,
    SubscriptionNotificationType.ON_HOLD: OnHoldNotificationHandler,
    SubscriptionNotificationType.IN_GRACE_PERIOD: GracePeriodNotificationHandler,
    SubscriptionNotificationType.RESTARTED: RestartedNotificationHandler,
    SubscriptionNotificationType.PRICE_CHANGE_CONFIRMED: IgnoreNotificationHandler,
    SubscriptionNotificationType.DEFERRED: DeferredNotificationHandler,
    SubscriptionNotificationType.PAUSED: PausedNotificationHandler,
    SubscriptionNotificationType.PAUSE_SCHEDULE_CHANGED: PausedScheduledNotificationHandler,
    SubscriptionNotificationType.REVOKED: RevokedNotificationHandler,
    SubscriptionNotificationType.EXPIRED: ExpiredNotificationHandler,
}


def _get_handler(event_id, notification_type):
    handler_class = _handlers.get(notification_type, UnknownNotificationHandler)
    return handler_class(event_id=event_id)


class SubscriptionNotificationProcessor(AbstractNotificationProcessor):
    """
    This notification is related to a subscription.
    """

    def __init__(self, payload):
        self.google_play_api = GooglePlayAPI()

        super(SubscriptionNotificationProcessor, self).__init__(payload)

    def process(self, event_id):
        data = self.data['subscriptionNotification']
        notification_type = data['notificationType']
        purchase_token = data['purchaseToken']
        google_subscription_id = data['subscriptionId']

        purchase = self.google_play_api.verify_purchase_token(
            event_id, google_subscription_id, purchase_token
        )

        if purchase is None:
            return ProcessingResult.FAIL

        info(event_id, f'Purchase {str(purchase)}')

        args = HandlerArgs(
            notification_type=int(notification_type),
            purchase_token=purchase_token,
            google_subscription_id=google_subscription_id,
            purchase=PurchaseSubscription(**purchase),
        )

        handler = _get_handler(event_id, notification_type)
        handler.log(data=args)

        try:
            return handler.handle(data=args)
        except NotificationError as ne:
            warning(event_id, str(ne))
            return ProcessingResult.FAIL
        except NotificationWarning as nw:
            warning(event_id, str(nw))
            return ProcessingResult.FAIL
