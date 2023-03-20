import logging
from datetime import datetime, timezone
from json.decoder import JSONDecodeError
from time import sleep

from django.conf import settings
from requests import Session
from requests.adapters import HTTPAdapter
from requests.exceptions import ConnectionError
from requests.packages.urllib3.util.retry import Retry

from amuse.vendor.apple.exceptions import (
    DuplicateAppleSubscriptionError,
    DuplicateAppleTransactionIDError,
    EmptyAppleReceiptError,
    MaxRetriesExceededError,
    UnknownAppleError,
)
from payments.models import PaymentTransaction
from subscriptions.models import Subscription
from subscriptions.vendor.apple.commons import parse_timestamp_ms

# See https://developer.apple.com/library/archive/technotes/tn2413/_index.html#//apple_ref/doc/uid/DTS40016228-CH1-RECEIPTURL
# Always verify your receipt first with the production URL; proceed to verify with the
# sandbox URL if you receive a 21007 status code. Following this approach ensures that
# you do not have to switch between URLs while your application is being tested or
# reviewed in the sandbox or is live in the App Store.
# The 21007 status code indicates that this receipt is a sandbox receipt, but it was
# sent to the production service for verification. A status of 0 indicates that the #
# receipt was properly verified.
APPLE_RETRY_TO_SANDBOX_STATUS = 21007
APPLE_SANDBOX_VALIDATION_URL = 'https://sandbox.itunes.apple.com/verifyReceipt'

logger = logging.getLogger('apple.subscription')


def get_request_session():
    session = Session()
    retry = Retry(
        total=3, read=3, connect=3, backoff_factor=0.3, status_forcelist=(500, 502, 504)
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount('https://', adapter)
    return session


class AppleReceiptValidationAPIClient:
    def __init__(self, receipt, request_id=None, max_retries=3):
        self.url = settings.APPLE_VALIDATION_URL
        self.receipt = receipt
        self.password = settings.APPLE_KEY
        self.session = get_request_session()
        self.max_retries = max_retries
        self.api_calls_count = 0
        self.backoff_factor = 1
        self.response_data = None
        self.sandbox_is_called = False
        self.request_id = request_id
        self.duplicate_transaction_found = False
        self.interactive_renewal = False
        self.restored_purchase = False

    def _get_apple_response(self):
        payload = {'password': self.password, 'receipt-data': self.receipt}
        logger.info(
            'Calling Apple API', extra={'request_id': self.request_id, 'url': self.url}
        )
        try:
            self.api_calls_count += 1
            response = self.session.post(self.url, json=payload)
            self.response_data = response.json()
            logger.info(
                'Apple response data',
                extra={
                    'request_id': self.request_id,
                    'response_data': self.response_data,
                },
            )
        except (ConnectionError, JSONDecodeError) as e:
            logger.info(
                'Apple response error data',
                extra={'request_id': self.request_id, 'apple_response_error': e},
            )
            self._retry()

    def validate_simple(self):
        self._get_apple_response()
        status = self.response_data['status']
        if status == 0:
            return True
        return False

    def _handle_response(self):
        status = self.response_data['status']
        if status == 0:
            logger.info(
                'Receipt validation were successful',
                extra={'request_id': self.request_id},
            )
        elif status == APPLE_RETRY_TO_SANDBOX_STATUS:
            self.url = APPLE_SANDBOX_VALIDATION_URL
            logger.info(
                'Status 21007 was received, retrying is in progress',
                extra={'request_id': self.request_id, 'url': self.url},
            )
            self.sandbox_is_called = True
            self.validate_receipt()
        elif self.response_data.get('is_retryable', False):
            self._retry()
        else:
            logger.error(
                'Validate receipt failed',
                extra={
                    'request_id': self.request_id,
                    'url': self.url,
                    'status': status,
                },
            )
            raise UnknownAppleError()

    def _get_latest_receipt(self):
        try:
            latest_receipt_info = self.response_data['latest_receipt_info']
            if len(latest_receipt_info) > 1:
                self.interactive_renewal = True
            active_transaction_id = self.response_data['pending_renewal_info'][0][
                'original_transaction_id'
            ]
            active_receipts = filter(
                lambda r: r['original_transaction_id'] == active_transaction_id,
                latest_receipt_info,
            )
            return sorted(active_receipts, key=lambda r: r['purchase_date_ms'])[-1]
        except KeyError as e:
            logger.info(
                'latest_receipt_info was not found in the response',
                extra={'request_id': self.request_id},
            )
            raise EmptyAppleReceiptError('An Empty receipt was received')

    def _get_receipt(self):
        return self._get_latest_receipt()

    def _is_duplicate_apple_transaction_id(self, transaction_id):
        queryset = PaymentTransaction.objects.filter(
            external_transaction_id=transaction_id
        )
        if queryset.exists():
            self.duplicate_transaction_found = True

    def get_transaction_id(self):
        receipt = self._get_receipt()
        transaction_id = receipt['transaction_id']
        self._is_duplicate_apple_transaction_id(transaction_id)
        if self.duplicate_transaction_found:
            logger.warning(
                f'AppleReceiptValidator request_id {self.request_id} tx {transaction_id} exist in DB'
            )
            raise DuplicateAppleTransactionIDError(
                'Transaction ID already exists in DB'
            )
        return transaction_id

    def _is_duplicate_apple_subscription(self, original_transaction_id, user):
        queryset = (
            Subscription.objects.active()
            .filter(
                payment_method__external_recurring_id=original_transaction_id,
                payment_method__method='AAPL',
            )
            .exclude(user=user)
        )

        return queryset.exists()

    def get_original_transaction_id(self, user=None):
        receipt = self._get_receipt()
        original_transaction_id = receipt['original_transaction_id']
        if user is not None and self._is_duplicate_apple_subscription(
            original_transaction_id, user
        ):
            logger.info(
                f'request_id {self.request_id} Active subscription with orig_txid {original_transaction_id} exist. user_id {user.id}'
            )
            raise DuplicateAppleSubscriptionError(
                'Active subscription with same original_transaction_id exist'
            )

        return original_transaction_id

    def get_product_id(self):
        receipt = self._get_receipt()
        return receipt['product_id']

    def get_expires_date(self):
        receipt = self._get_receipt()
        expires_date_timestamp = get_expires_date_timestamp(receipt)

        return parse_expires_date(expires_date_timestamp)

    def get_purchase_date(self):
        last_transaction = self._get_receipt()
        purchase_date_ms = last_transaction.get('purchase_date_ms')
        purchase_date = parse_timestamp_ms(purchase_date_ms)
        if purchase_date.date() < datetime.utcnow().date():
            self.restored_purchase = True
        return purchase_date

    def _get_first_pending_renewal_info(self):
        return self.response_data['pending_renewal_info'][0]

    def get_auto_renew_status(self):
        if self.sandbox_is_called:
            auto_renew_status = self.response_data['auto_renew_status']
        else:
            pending_renewal_info = self._get_first_pending_renewal_info()
            auto_renew_status = pending_renewal_info['auto_renew_status']

        return int(auto_renew_status)

    def get_is_in_intro_offer(self):
        receipt = self._get_receipt()
        return receipt.get('is_in_intro_offer_period', False) in [
            True,
            'true',
            'True',
            '1',
        ]

    def is_introductory_offer_eligible(self):
        """
        In the receipt, check the values of the is_trial_period and the
        is_in_intro_offer_period for all in-app purchase transactions. If either of
        these fields are true for a given subscription, the user is not eligible for
        an introductory offer on that subscription product or any other products within
        the same subscription group.

        More Info:
        https://developer.apple.com/documentation/storekit/original_api_for_in-app_purchase/subscriptions_and_offers/implementing_introductory_offers_in_your_app
        """
        items = self.response_data.get('latest_receipt_info', [])

        receipt_info = next(
            (
                x
                for x in items
                if x.get('is_in_intro_offer_period', 'false') == 'true'
                or x.get('is_trial_period', 'false') == 'true'
            ),
            None,
        )

        return not receipt_info

    def _retry(self):
        logger.info(
            f'Retry calling Apple API after {self.backoff_factor} seconds',
            extra={'request_id': self.request_id, 'url': self.url},
        )
        sleep(self.backoff_factor)
        self.backoff_factor *= 2
        self.validate_receipt()

    def validate_receipt(self):
        if self.api_calls_count < self.max_retries:
            self._get_apple_response()
            self._handle_response()
        else:
            logger.info(
                f'Maximum retries of {self.max_retries} was excceeded, giving up',
                extra={'request_id': self.request_id, 'url': self.url},
            )
            raise MaxRetriesExceededError()


def get_expires_date_timestamp(receipt):
    if 'expires_date_ms' in receipt:
        expires_date_timestamp = receipt['expires_date_ms']
    else:
        expires_date_timestamp = receipt['expires_date']

    return float(expires_date_timestamp) / 1000


def parse_expires_date(expires_date_timestamp):
    timestamp = expires_date_timestamp
    expires_date = datetime.utcfromtimestamp(timestamp)

    return expires_date.astimezone(timezone.utc)


def parse_auto_renew_status(auto_renew_status_string):
    return auto_renew_status_string == 'true'


def get_receipt(payload):
    if 'latest_receipt_info' in payload:
        latest_receipt_info = payload['latest_receipt_info']
    else:
        latest_receipt_info = payload['latest_expired_receipt_info']

    expires_date_timestamp = get_expires_date_timestamp(latest_receipt_info)
    expires_date = parse_expires_date(expires_date_timestamp)
    auto_renew_status = parse_auto_renew_status(payload['auto_renew_status'])

    return {
        'notification_type': payload['notification_type'],
        'product_id': latest_receipt_info['product_id'],
        'transaction_id': latest_receipt_info['transaction_id'],
        'original_transaction_id': latest_receipt_info['original_transaction_id'],
        'expires_date': expires_date,
        'auto_renew_status': auto_renew_status,
    }
