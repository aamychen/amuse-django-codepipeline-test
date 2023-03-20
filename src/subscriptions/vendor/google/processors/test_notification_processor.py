from .abstract_notification_processor import AbstractNotificationProcessor
from ..helpers import info
from ..enums import ProcessingResult


class TestNotificationProcessor(AbstractNotificationProcessor):
    """
    Test notification is related to a test publish.
    These are sent only through the Google Play Developer Console

    We should return status=200.
    """

    __test__ = False

    def process(self, event_id):
        info(
            event_id,
            f'Received a Test Realtime Developer Notification. {str(self.data)}',
        )
        return ProcessingResult.SUCCESS
