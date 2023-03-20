from .abstract_notification_processor import AbstractNotificationProcessor

from ..helpers import info
from ..enums import ProcessingResult


class UnknownNotificationProcessor(AbstractNotificationProcessor):
    """
    This should never happen.

    Indicates something went wrong e.g.:
        - google added additional notification type and we are not aware of it;
        - or we received invalid request.
    """

    def process(self, event_id):
        info(
            event_id,
            f'Received a Unknown Realtime Notification. Not supported. {str(self.data)}',
        )
        return ProcessingResult.FAIL
