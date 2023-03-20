import base64
import json

from .enums import ProcessingResult
from .processors import (
    OneTimeNotificationProcessor,
    SubscriptionNotificationProcessor,
    TestNotificationProcessor,
    UnknownNotificationProcessor,
)

from .google_play_api import GooglePlayAPI
from .helpers import info, warning
from .duplicate_notification_checker import check_duplicate_notifications


def _get_notification_processor(payload):
    """
    Returns valid notification processor.

    NOTE that 'subscriptionNotification' and 'oneTimePurchaseNotification' and 'testNotification' fields are mutually exclusive.

    Also NOTE that this IS NOT subscription-notification-type (e.g. PURCHASE, CANCEL, RENEW etc.).
    """
    if payload.get('subscriptionNotification') is not None:
        return SubscriptionNotificationProcessor(payload)

    if payload.get('testNotification') is not None:
        return TestNotificationProcessor(payload)

    if payload.get('oneTimePurchaseNotification') is not None:
        return OneTimeNotificationProcessor(payload)

    return UnknownNotificationProcessor(payload)


class GoogleBillingNotificationProcessor(object):
    def __init__(self, event_id):
        self._google_play_api = GooglePlayAPI()

        self._event_id = event_id

    def _decode_payload(self, payload):
        message = payload.get('message')

        if message is None:
            info(self._event_id, "Invalid payload. 'Message' missing")
            return None

        # Each publish made to a Cloud Pub/Sub topic contains a single base64-encoded data field.
        encoded_data = message.get('data')
        if encoded_data is None:
            info(self._event_id, "Invalid payload. Message 'data' missing")
            return None

        data = None
        try:
            decoded_data = base64.standard_b64decode(encoded_data).decode('utf-8')
            data = json.loads(decoded_data)
            info(self._event_id, f'Decoded data: {str(data)}')
        except Exception as ex:
            warning(self._event_id, str(ex))

        return data

    def process(self, payload):
        """
        Validate and process google billing notification received from Google Pub Sub.
        """
        decoded_payload = self._decode_payload(payload)

        if decoded_payload is None:
            return ProcessingResult.FAIL

        return self.run_process(payload, decoded_payload)

    @check_duplicate_notifications
    def run_process(self, payload, decoded_payload):
        processor = _get_notification_processor(decoded_payload)

        return processor.process(self._event_id)
