from django.utils.translation import gettext_lazy as _
from rest_framework import status
from rest_framework.exceptions import APIException


class BadQueryParameterException(Exception):
    pass


class Adyen3DSRequiredError(BaseException):
    def __init__(self, adyen_response):
        self.adyen_response = adyen_response


class WrongAPIversionError(APIException):
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = _('API version is not supported.')
    default_code = 'api_version_error'


class MissingQueryParameterError(APIException):
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = _('Artist ID is missing from query parameters.')
    default_code = 'missing_query_parameter_error'


class MissingSongOwnershipError(APIException):
    status_code = status.HTTP_403_FORBIDDEN
    default_detail = _('You need to be owner of the song to have access.')
    default_code = 'missing_song_ownership_error'


class ProPermissionError(APIException):
    status_code = status.HTTP_403_FORBIDDEN
    default_detail = _('You need to upgrade to Pro to access this feature.')
    default_code = 'pro_permission_error'


class ActiveSubscriptionExistsError(APIException):
    status_code = status.HTTP_403_FORBIDDEN
    default_detail = _('You already have an active subscription.')
    default_code = 'artive_subcription_exists_error'


class NoActiveSubscriptionExistsError(APIException):
    status_code = status.HTTP_404_NOT_FOUND
    default_detail = _('You have no active paid subscription.')
    default_code = 'missing_subcription_error'


class SubscriptionProviderMismatchError(APIException):
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = _('Subscription Provider Mismatch Error')
    default_code = 'subscription_provider_mismatch_error'


class ReleaseDoesNotExist(APIException):
    status_code = status.HTTP_404_NOT_FOUND
    default_detail = _('Release ID does not exit')
    default_code = 'missing_release_error'


class AppleServerError(APIException):
    status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
    default_code = 'apple_receipt_validation_error'


class SubscriptionPlanDoesNotExist(APIException):
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = _('Subscription Plan does not exist')
    default_code = 'subscription_plan_does_not_exist'


class WithdrawalMethodNotSupported(APIException):
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = _('Withdrawal method not supported')
    default_code = 'withdrawal_method_not_supported'
