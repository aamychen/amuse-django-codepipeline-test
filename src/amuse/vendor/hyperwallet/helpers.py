import logging

from django.conf import settings
from rest_framework.serializers import ValidationError
from waffle import flag_is_active

from amuse.utils import (
    FakePhoneNumberError,
    InvalidPhoneNumberError,
    convert_to_positive_and_round,
    format_phonenumber,
)
from amuse.vendor.hyperwallet.client import check_account_exists
from amuse.vendor.hyperwallet.exceptions import HyperwalletAPIError
from users.models import User


logger = logging.getLogger(__name__)


EMAIL_VALIDATION_MSG = "The provided email does not match your Hyperwallet account email or any of your Paypal accounts registered at Hyperwallet. You have to add the new Paypal account at Hyperwallet before you can make a withdrawal with it or enter your Hyperwallet account email."
API_ERROR_MSG = "An unexpected error occured. Please try again in a while."
PHONE_ERROR_MSG = "Your Amuse account phone number is not valid. Please go to Account -> User Profile and update your phone number and try to make a withdrawal again."
DUPLICATE_EMAIL_VALIDATION_MSG = "Please use another email address."


def is_amount_within_limit(request, amount, is_valid_royalty_advance):
    min_limit = settings.HYPERWALLET_MIN_WITHDRAWAL_LIMIT

    if is_valid_royalty_advance:
        max_limit = settings.HYPERWALLET_MAX_ADVANCE_WITHDRAWAL_LIMIT
    elif flag_is_active(request, 'vendor:hyperwallet:override-max-limit'):
        max_limit = settings.HYPERWALLET_VERIFIED_USERS_MAX_WITHDRAWAL_LIMIT
    else:
        max_limit = settings.HYPERWALLET_MAX_WITHDRAWAL_LIMIT

    # The amount we're sending in here is already positive but we keep the
    # convert_to_positive_and_round helper as it is to maintain compatibility
    # with other code that uses it and doing abs() does always return positive
    # numbers anyway.
    rounded_amount = convert_to_positive_and_round(amount)
    return min_limit <= rounded_amount <= max_limit


def check_hyperwallet_is_active(request, amount, is_valid_royalty_advance):
    hyperwallet_flag_is_active = flag_is_active(request._request, 'vendor:hyperwallet')
    is_excluded_from_hyperwallet = flag_is_active(
        request._request, 'vendor:hyperwallet:excluded'
    )
    is_within_limit = is_amount_within_limit(
        request._request, amount, is_valid_royalty_advance
    )
    is_active_user = request.user.is_active

    criterias = [
        hyperwallet_flag_is_active,
        not is_excluded_from_hyperwallet,
        is_within_limit,
        is_active_user,
    ]

    if is_valid_royalty_advance:
        is_not_flagged_user = request.user.category != User.CATEGORY_FLAGGED
        criterias.append(is_not_flagged_user)

    return all(criterias)


def hyperwallet_validate_email(user, email):
    try:
        account_already_exists = check_account_exists(email)
    except HyperwalletAPIError as e:
        logging.exception(e)
        raise ValidationError({'email': [API_ERROR_MSG]})

    if account_already_exists:
        raise ValidationError({'email': [DUPLICATE_EMAIL_VALIDATION_MSG]})


def validate_phone(user):
    """
    The user need a valid phone number in order to create a new Hyperwallet account
    so we validate that `User.phone` is valid.

    We only need to validate the phone number if the user does not have a
    hyperwallet account as it's only used as an activation parameter when creating
    the account.
    """
    validated_phone = None

    try:
        validated_phone = format_phonenumber(user.phone, user.country)
    except (FakePhoneNumberError, InvalidPhoneNumberError):
        raise ValidationError({'non_field_errors': [PHONE_ERROR_MSG]})

    return validated_phone
