from .abstract_notification_processor import AbstractNotificationProcessor
from ..helpers import info
from ..enums import ProcessingResult


class OneTimeNotificationProcessor(AbstractNotificationProcessor):
    """
    OneTime notification is related to a one-time purchase,
    and this field contains additional information related to the purchase.

    Amuse does not support one-time purchase.
    If we receive this type, then something went wrong!
    """

    def process(self, event_id):
        info(
            event_id,
            f'Received a One-Time-Purchase Realtime Notification. Not supported. {str(self.data)}',
        )
        return ProcessingResult.FAIL
