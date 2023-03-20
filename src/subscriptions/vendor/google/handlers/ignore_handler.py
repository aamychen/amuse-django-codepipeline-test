from .abstract_handler import AbstractNotificationHandler
from .containers import HandlerArgs

from ..enums import ProcessingResult, SubscriptionNotificationType
from ..helpers import info


class IgnoreNotificationHandler(AbstractNotificationHandler):
    """
    Some notification are intentionally ignored.

    Example: PURCHASED notification is ignored; when purchased, subscription is handled
    by `POST /api/subscriptions/google/` endpoint which is called directly from the device.
    """

    def log(self, data: HandlerArgs):
        info(
            self.event_id,
            f'Ignored notificationType: {SubscriptionNotificationType(data.notification_type).name}',
        )

    def handle(self, data: HandlerArgs):
        return ProcessingResult.SUCCESS
