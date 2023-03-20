from .abstract_handler import AbstractNotificationHandler
from .containers import HandlerArgs
from ..enums import ProcessingResult
from ..helpers import warning


class UnknownNotificationHandler(AbstractNotificationHandler):
    """
    This should never happen.
    """

    def log(self, data: HandlerArgs):
        warning(self.event_id, f'Unknown notificationType: {data.notification_type}')

    def handle(self, data: HandlerArgs):
        return ProcessingResult.FAIL
