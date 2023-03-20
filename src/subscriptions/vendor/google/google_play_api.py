import json
from base64 import b85decode

from django.conf import settings
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import Error, HttpError

from .helpers import warning

SERVICE_NAME = 'androidpublisher'
SERVICE_VERSION = 'v3'
SCOPES = ['https://www.googleapis.com/auth/androidpublisher']

_credentials = None


def _load_credentials():
    service_account_decoded = b85decode(
        settings.GOOGLE_PLAY_API_SERVICE_ACCOUNT
    ).decode('utf-8')

    service_account_dict = json.loads(service_account_decoded)

    return service_account.Credentials.from_service_account_info(
        service_account_dict, scopes=SCOPES
    )


def _get_credentials():
    """
    Loads (only once) and returns google service account.
    """
    global _credentials
    if _credentials is None:
        _credentials = _load_credentials()

    return _credentials


class GooglePlayAPI(object):
    """
    The Google Play Developer API allows you to perform a number of publishing and app-management tasks.

    It includes two components:
        - The Subscriptions and In-App Purchases API lets you manage in-app purchases and subscriptions.
        - The Publishing API lets you upload and publish apps, and perform other publishing-related tasks.

    This implementation will focus on the first component: The Subscriptions and In-App Purchases API.

    https://developers.google.com/android-publisher#subscriptions
    """

    @staticmethod
    def verify_purchase_token(
        event_id, subscription_id, purchase_token, raise_exception=False
    ):
        """
        Checks whether a user's subscription purchase is valid and returns a SubscriptionPurchase object.

        https://developers.google.com/android-publisher/api-ref/rest/v3/purchases.subscriptions/get
        """
        credentials = _get_credentials()
        with build(
            SERVICE_NAME,
            SERVICE_VERSION,
            credentials=credentials,
            cache_discovery=False,
        ) as service:
            try:
                subs = service.purchases().subscriptions()
                return subs.get(
                    packageName=settings.ANDROID_APP_PACKAGE,
                    subscriptionId=subscription_id,
                    token=purchase_token,
                ).execute()
            except Error as ex:
                warning(
                    event_id,
                    f'Unable to verify purchase token, token={purchase_token}, subscriptionId={subscription_id}, error="{str(ex)}"',
                )
                if raise_exception:
                    raise

            return None

    @staticmethod
    def acknowledge(event_id, subscription_id, purchase_token):
        """
        Checks whether a user's subscription purchase is valid and returns a SubscriptionPurchase object.

        https://developers.google.com/android-publisher/api-ref/rest/v3/purchases.subscriptions/get
        """
        credentials = _get_credentials()
        with build(
            SERVICE_NAME,
            SERVICE_VERSION,
            credentials=credentials,
            cache_discovery=False,
        ) as service:
            try:
                subs = service.purchases().subscriptions()
                return subs.acknowledge(
                    packageName=settings.ANDROID_APP_PACKAGE,
                    subscriptionId=subscription_id,
                    token=purchase_token,
                ).execute()
            except Error as ex:
                warning(
                    event_id,
                    f'Unable to acknowledge purchase, token={purchase_token}, subscriptionId={subscription_id}, error="{str(ex)}"',
                )

            return None

    @staticmethod
    def cancel(event_id, subscription_id, purchase_token):
        """
        Cancels a user's subscription purchase.
        The subscription remains valid until its expiration time.

        https://developers.google.com/android-publisher/api-ref/rest/v3/purchases.subscriptions/cancel
        https://androidpublisher.googleapis.com/androidpublisher/v3/applications/{packageName}/purchases/subscriptions/{subscriptionId}/tokens/{token}:cancel
        """
        result = dict(success=False, message='')
        credentials = _get_credentials()
        with build(
            SERVICE_NAME,
            SERVICE_VERSION,
            credentials=credentials,
            cache_discovery=False,
        ) as service:
            try:
                subs = service.purchases().subscriptions()
                subs.cancel(
                    packageName=settings.ANDROID_APP_PACKAGE,
                    subscriptionId=subscription_id,
                    token=purchase_token,
                ).execute()

                result['success'] = True
            except HttpError as ex:
                warning(
                    event_id,
                    f'Unable to cancel, token={purchase_token}, subscriptionId={subscription_id}, error="{str(ex)}"',
                )

                result['message'] = ex.error_details

            return result

    @staticmethod
    def defer(
        event_id, subscription_id, purchase_token, expiry_timestamp, defer_timestamp
    ):
        """
        Defers a user's subscription purchase until a specified future expiration time.

        https://developers.google.com/android-publisher/api-ref/rest/v3/purchases.subscriptions/defer
        https://androidpublisher.googleapis.com/androidpublisher/v3/applications/{packageName}/purchases/subscriptions/{subscriptionId}/tokens/{token}:defer
        """
        result = dict(success=False, message='')
        credentials = _get_credentials()
        with build(
            SERVICE_NAME,
            SERVICE_VERSION,
            credentials=credentials,
            cache_discovery=False,
        ) as service:
            try:
                subs = service.purchases().subscriptions()
                response = subs.defer(
                    packageName=settings.ANDROID_APP_PACKAGE,
                    subscriptionId=subscription_id,
                    token=purchase_token,
                    body={
                        'deferralInfo': {
                            'expectedExpiryTimeMillis': str(expiry_timestamp),
                            'desiredExpiryTimeMillis': str(defer_timestamp),
                        }
                    },
                ).execute()

                result['success'] = True
            except HttpError as ex:
                warning(
                    event_id,
                    f'Unable to defer, token={purchase_token}, subscriptionId={subscription_id}, error="{str(ex)}"',
                )

                result['message'] = ex.error_details

            return result

    @staticmethod
    def refund(event_id, subscription_id, purchase_token):
        """
        Refunds a user's subscription purchase, but the subscription remains valid
        until its expiration time and it will continue to recur.

        https://developers.google.com/android-publisher/api-ref/rest/v3/purchases.subscriptions/refund
        https://androidpublisher.googleapis.com/androidpublisher/v3/applications/{packageName}/purchases/subscriptions/{subscriptionId}/tokens/{token}:refund
        """
        result = dict(success=False, message='')
        credentials = _get_credentials()
        with build(
            SERVICE_NAME,
            SERVICE_VERSION,
            credentials=credentials,
            cache_discovery=False,
        ) as service:
            try:
                subs = service.purchases().subscriptions()
                subs.refund(
                    packageName=settings.ANDROID_APP_PACKAGE,
                    subscriptionId=subscription_id,
                    token=purchase_token,
                ).execute()

                result['success'] = True
            except HttpError as ex:
                warning(
                    event_id,
                    f'Unable to refund, token={purchase_token}, subscriptionId={subscription_id}, error="{str(ex)}"',
                )

                result['message'] = ex.error_details

            return result

    @staticmethod
    def revoke(event_id, subscription_id, purchase_token):
        """
        Refunds and immediately revokes a user's subscription purchase.
        Access to the subscription will be terminated immediately and it will stop recurring.

        https://developers.google.com/android-publisher/api-ref/rest/v3/purchases.subscriptions/revoke
        https://androidpublisher.googleapis.com/androidpublisher/v3/applications/{packageName}/purchases/subscriptions/{subscriptionId}/tokens/{token}:revoke
        """
        result = dict(success=False, message='')
        credentials = _get_credentials()
        with build(
            SERVICE_NAME,
            SERVICE_VERSION,
            credentials=credentials,
            cache_discovery=False,
        ) as service:
            try:
                subs = service.purchases().subscriptions()
                subs.revoke(
                    packageName=settings.ANDROID_APP_PACKAGE,
                    subscriptionId=subscription_id,
                    token=purchase_token,
                ).execute()

                result['success'] = True
            except HttpError as ex:
                warning(
                    event_id,
                    f'Unable to revoke, token={purchase_token}, subscriptionId={subscription_id}, error="{str(ex)}"',
                )

                result['message'] = ex.error_details

            return result

    @staticmethod
    def voided(event_id, subscription_id, purchase_token):
        """
        Refunds and immediately revokes a user's subscription purchase.
        Access to the subscription will be terminated immediately and it will stop recurring.

        https://developers.google.com/android-publisher/api-ref/rest/v3/purchases.voidedpurchases/list
        https://androidpublisher.googleapis.com/androidpublisher/v3/applications/{packageName}/purchases/voidedpurchases
        """
        result = dict(success=False, message='')
        credentials = _get_credentials()
        with build(
            SERVICE_NAME,
            SERVICE_VERSION,
            credentials=credentials,
            cache_discovery=False,
        ) as service:
            try:
                subs = service.purchases().voidedpurchases()
                return subs.list(
                    packageName=settings.ANDROID_APP_PACKAGE, type=1
                ).execute()

                result['success'] = True
            except HttpError as ex:
                warning(event_id, ex)

                result['message'] = ex.error_details

            return result
