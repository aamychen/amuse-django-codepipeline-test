from amuse.logging import logger
from payouts.notifications.hw_user_notification_handler import HWUserNotificationHandler
from payouts.notifications.hw_payment_notification_handler import (
    HWPaymentNotificationHandler,
)
from payouts.notifications.hw_trm_notification_handler import (
    HWTransferMethodNotificationHandler,
)


class HyperWalletNotificationHandler(object):
    def __init__(self, payload):
        self.payload = payload

    def _is_payload_valid(self):
        """
        Basic input validator
        :return: bool
        """
        check_list = list()
        try:
            check_list.append("object" in self.payload)
            check_list.append(isinstance(self.payload['object'], dict))
            check_list.append("token" in self.payload['object'])
            check_list.append("status" in self.payload['object'])
            return all(check_list)
        except Exception as e:
            logger.warning(
                f"Hyperwalet main handler invalid payload {self.payload} error {e}"
            )
            return False

    def process_notification(self):
        if not self._is_payload_valid():
            return {"is_success": False, "reason": "Invalid payload"}
        token = self.payload['object']['token']
        if token.startswith('usr'):
            return HWUserNotificationHandler(payload=self.payload).handle()
        elif token.startswith('trm'):
            return HWTransferMethodNotificationHandler(payload=self.payload).handle()
        elif token.startswith('pmt'):
            return HWPaymentNotificationHandler(payload=self.payload).handle()
        else:
            logger.warning(
                f"Hyperwalet main handler unknown notification {self.payload}"
            )
            return {"is_success": False, "reason": "UNKNOWN_TOKEN_TYPE"}
