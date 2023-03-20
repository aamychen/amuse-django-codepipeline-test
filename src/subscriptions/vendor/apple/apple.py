from uuid import uuid4
from amuse.logging import logger
from django.http import HttpResponse
from rest_framework import status
from amuse.vendor.apple.subscriptions import AppleReceiptValidationAPIClient
from subscriptions.vendor.apple.initial_buy_handler import InitialBuyHandelr
from subscriptions.vendor.apple.renew_handler import RenewHandler
from subscriptions.vendor.apple.cancel_handler import CancelHandler
from subscriptions.vendor.apple.interactive_renewal_handler import (
    InteractiveRenewalHandler,
)
from subscriptions.vendor.apple.change_renewal_handler import ChangeRenewalHandler
from subscriptions.vendor.apple.plan_change_downgrade_handelr import (
    PlanChangeDowgradeHandler,
)


class AppleNotificationHandler(object):
    def __init__(self):
        self.id = uuid4()
        self.receipt_validator = AppleReceiptValidationAPIClient
        self.handlers = {
            'INITIAL_BUY': InitialBuyHandelr,
            'DID_RENEW': RenewHandler,
            'DID_RECOVER': RenewHandler,
            'DID_FAIL_TO_RENEW': RenewHandler,
            'CANCEL': CancelHandler,
            'DID_CHANGE_RENEWAL_PREF': PlanChangeDowgradeHandler,
            'INTERACTIVE_RENEWAL': InteractiveRenewalHandler,
            'DID_CHANGE_RENEWAL_STATUS': ChangeRenewalHandler,
        }

    def is_receipt_valid(self, payload):
        self.receipt_validator(payload['unified_receipt']['latest_receipt'])
        return self.receipt_validator.validate_simple()

    def is_payload_valid(self, payload):
        try:
            n_type = payload.get('notification_type')
            unified = payload.get('unified_receipt')
            last_recipit_info = unified.get('latest_receipt_info')
            pending_renewals = unified.get('pending_renewal_info')
            if all(
                v is not None
                for v in [unified, last_recipit_info, pending_renewals, n_type]
            ):
                return True
        except Exception as e:
            logger.warning(
                f'txid ={self.id} Failed to validate apple notification error {e}: {payload}'
            )
            return False

    def process_notification(self, payload):
        is_data_valid = self.is_payload_valid(payload)
        if is_data_valid is None or is_data_valid == False:
            return HttpResponse(status=status.HTTP_400_BAD_REQUEST)

        notification_type = payload.get('notification_type', None)
        handler = self.handlers.get(notification_type, None)
        if handler is None:
            logger.warning(f'Apple {notification_type} handler not implemented')
            return HttpResponse(status=status.HTTP_200_OK)
        else:
            return handler().handle(payload)
