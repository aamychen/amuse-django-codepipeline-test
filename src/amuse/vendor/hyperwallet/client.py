import json
import logging
import requests
import time

from django.conf import settings

from amuse.utils import convert_to_positive_and_round
from amuse.vendor.hyperwallet.exceptions import (
    HyperwalletAPIError,
    LimitSubceededError,
    FirstNameConstraintError,
    LastNameConstraintError,
    IncorrectFundingProgramError,
    InvalidWalletStatusError,
    StoreInvalidCurrencyError,
    DuplicateExtraIdTypeError,
)
from amuse.vendor.revenue.client import update_withdrawal
from slayer.clientwrapper import update_royalty_advance_offer
from slayer import exceptions
from releases.models import RoyaltySplit
from users.models import User


logger = logging.getLogger(__name__)

HEADERS = {'Content-Type': 'application/json', 'Accept': 'application/json'}
ALLOWED_ENDPOINTS = ["users", "payments"]
ERROR_DICT = {
    "LIMIT_SUBCEEDED": LimitSubceededError,
    "INCORRECT_FUNDING_PROGRAM": IncorrectFundingProgramError,
    "INVALID_WALLET_STATUS": InvalidWalletStatusError,
    "STORE_INVALID_CURRENCY": StoreInvalidCurrencyError,
    "DUPLICATE_EXTRA_ID_TYPE": DuplicateExtraIdTypeError,
    "CONSTRAINT_VIOLATIONS_FIRST_NAME": FirstNameConstraintError,
    "CONSTRAINT_VIOLATIONS_LAST_NAME": LastNameConstraintError,
}


def get_user_payload(payload):
    """
    Payload that is to be POSTed at `HYPERWALLET_ENDPOINT/users`. phoneNumber must be
    included as it's used as the activation parameter.
    """
    user = User.objects.get(pk=payload["user_id"])

    program_token = get_program_token(user.country)

    data = {
        "clientUserId": user.id,
        "email": payload["email"],
        "profileType": "INDIVIDUAL",
        "programToken": program_token,
        "phoneNumber": payload["user_validated_phone"],
        "firstName": user.first_name,
        "lastName": user.last_name,
        "country": user.country,
    }

    if payload.get("postal_code"):
        data["postalCode"] = payload["postal_code"]

    return data


def get_payment_payload(payload):
    user = User.objects.get(pk=payload["user_id"])
    program_token = get_program_token(user.country)
    rounded_amount = convert_to_positive_and_round(payload["amount"])

    return {
        "amount": rounded_amount.__str__(),
        "clientPaymentId": payload["transaction_id"],
        "currency": "USD",
        "destinationToken": payload["hyperwallet_user_token"],
        "programToken": program_token,
        "purpose": "OTHER",
    }


def get_program_token(country_code):
    if country_code == "SE":
        program_token = settings.HYPERWALLET_PROGRAM_TOKEN_SE
    elif country_code in settings.EU_COUNTRIES:
        program_token = settings.HYPERWALLET_PROGRAM_TOKEN_EU
    else:
        program_token = settings.HYPERWALLET_PROGRAM_TOKEN_REST_OF_WORLD

    return program_token


def create_user(payload):
    user_payload = get_user_payload(payload)

    try:
        r = create("users", user_payload)
    except HyperwalletAPIError as e:
        if payload.get("is_valid_royalty_advance"):
            cancel_royalty_advance(payload)
        else:
            cancel_standard_withdrawal(payload)
        raise e

    response = r.json()

    logger.info(
        "Create Hyperwallet user %s succeeded with token %s."
        % (payload["user_id"], response["token"])
    )

    return response


def create_payment(payload, delay=None):
    if delay:
        time.sleep(delay)

    if payload.get("is_valid_royalty_advance"):
        process_func = {
            "post_process": post_process_royalty_advance,
            "cancel_process": cancel_royalty_advance,
        }
    else:
        process_func = {
            "post_process": post_process_standard_withdrawal,
            "cancel_process": cancel_standard_withdrawal,
        }

    payment_payload = get_payment_payload(payload)

    try:
        r = create("payments", payment_payload)
    except HyperwalletAPIError as e:
        process_func["cancel_process"](payload)
        raise e

    response = r.json()

    payload["description"]["hyperwallet_payment_token"] = response["token"]
    payload["description"]["hyperwallet_user_token"] = response["destinationToken"]
    payload["description"]["program_token"] = response["programToken"]

    process_func["post_process"](payload)


def create(endpoint, payload):
    assert endpoint in ALLOWED_ENDPOINTS

    payload_json = json.dumps(payload)

    logger.info("Hyperwallet payload %s" % payload_json)

    response = requests.post(
        url="%s/%s" % (settings.HYPERWALLET_ENDPOINT, endpoint),
        data=payload_json,
        headers=HEADERS,
        auth=(settings.HYPERWALLET_USER, settings.HYPERWALLET_PASSWORD),
    )

    logger.info(
        "Hyperwallet response %s status %s",
        json.loads(response.content),
        response.status_code,
    )

    if response.status_code != 201:
        hyperwallet_error = json.loads(response.content)["errors"][0]
        error_code = hyperwallet_error["code"]

        if error_code == "CONSTRAINT_VIOLATIONS":
            if hyperwallet_error["fieldName"] == "firstName":
                error_code = "CONSTRAINT_VIOLATIONS_FIRST_NAME"
            elif hyperwallet_error["fieldName"] == "lastName":
                error_code = "CONSTRAINT_VIOLATIONS_LAST_NAME"

        hyperwallet_exception = ERROR_DICT.get(error_code, HyperwalletAPIError)

        raise hyperwallet_exception(
            "Create Hyperwallet %s with payload %s failed with statuscode %s and errors %s."
            % (endpoint, payload_json, response.status_code, hyperwallet_error)
        )

    return response


def get(endpoint, allowed_response_codes=[200], params=None):
    logger.info("Hyperwallet get %s" % endpoint)

    response = requests.get(
        url="%s/%s" % (settings.HYPERWALLET_ENDPOINT, endpoint),
        headers=HEADERS,
        auth=(settings.HYPERWALLET_USER, settings.HYPERWALLET_PASSWORD),
        params=params,
    )

    if response.status_code not in allowed_response_codes:
        raise HyperwalletAPIError(
            "Get Hyperwallet %s with statuscode %s and errors %s."
            % (endpoint, response.status_code, response)
        )
    else:
        logger.info("Hyperwallet response %s %s" % (endpoint, response))

    return response


def check_account_exists(email):
    """
    A user with the given email address either exists (200) or not (204) so we don't
    expect to get back any other status codes unless Hyperwallet's api returns an error.
    """
    endpoint = 'users'
    params = {'email': email}
    try:
        r = get(endpoint, [200, 204], params)
    except HyperwalletAPIError as e:
        raise e

    if r.status_code == 200:
        return True
    elif r.status_code == 204:
        return False
    else:
        raise HyperwalletAPIError()


def get_payments(created_after, created_before, limit=100, offset=0):
    endpoint = "payments"
    params = {
        "createdAfter": created_after,
        "createdBefore": created_before,
        "limit": limit,
        "offset": offset,
    }

    try:
        response = get(endpoint, [200, 204], params)
    except HyperwalletAPIError as e:
        raise e

    return response.json() if response.status_code == 200 else None


def post_process_standard_withdrawal(payload):
    transaction_id = update_withdrawal(
        payload["transaction_id"], "is_complete", description=payload["description"]
    )

    if transaction_id:
        logger.info(
            "Create Hyperwallet payment for transaction %s succeeded with token %s."
            % (
                payload["transaction_id"],
                payload["description"]["hyperwallet_payment_token"],
            )
        )
    else:
        logger.error(
            "update_withdrawal is_complete for user_id %s and transaction_id %s failed"
            % (payload["user_id"], payload["transaction_id"])
        )


def cancel_standard_withdrawal(payload):
    transaction_id = update_withdrawal(payload["transaction_id"], "is_cancelled")

    if transaction_id:
        logger.info(
            "update_withdrawal is_cancelled for user_id %s and transaction_id %s succeeded",
            payload["user_id"],
            payload["transaction_id"],
        )
    else:
        logger.error(
            "update_withdrawal is_cancelled for user_id %s and transaction_id %s failed",
            payload["user_id"],
            payload["transaction_id"],
        )


def post_process_royalty_advance(payload):
    """
    We will not catch these exceptions as we want it to fail hard so we get notified
    in Sentry and then we'll need to update the flags manually in Slayer.
    """
    response = update_royalty_advance_offer(
        user_id=payload["user_id"],
        advance_id=payload["royalty_advance_id"],
        action="activate",
        description=payload["description"],
    )
    if not response:
        raise exceptions.RoyaltyAdvanceActivateError


def cancel_royalty_advance(payload, unlock_splits=True):
    """
    We will not catch these exceptions as we want it to fail hard so we get notified
    in Sentry and then we'll need to update the flags manually in Slayer.
    """
    if unlock_splits:
        split_ids_to_lock = payload.get("split_ids_to_lock")

        if split_ids_to_lock:
            split_ids_len = len(split_ids_to_lock)

            if split_ids_len > 0:
                split_ids_to_update = list(
                    RoyaltySplit.objects.filter(
                        id__in=split_ids_to_lock,
                        user_id=payload["user_id"],
                        status=RoyaltySplit.STATUS_ACTIVE,
                        is_locked=True,
                    ).values_list("id", flat=True)
                )

                if sorted(split_ids_to_update) == sorted(split_ids_to_lock):
                    RoyaltySplit.objects.filter(id__in=split_ids_to_update).update(
                        is_locked=False
                    )
                    logger.info(
                        "Royalty advance %s user_id %s unlocked splits %s.",
                        payload["royalty_advance_id"],
                        payload["user_id"],
                        split_ids_to_lock,
                    )
                else:
                    logger.warning(
                        "Royalty advance %s user_id %s unlock splits %s failed as it doesn't match %s splits returned from the database.",
                        payload["royalty_advance_id"],
                        payload["user_id"],
                        split_ids_to_lock,
                        split_ids_to_update,
                    )

    response = update_royalty_advance_offer(
        user_id=payload["user_id"],
        advance_id=payload["royalty_advance_id"],
        action="cancel",
        description=payload["description"],
    )

    if not response:
        raise exceptions.RoyaltyAdvanceCancelError

    logger.info(
        "Royalty advance offer %s user_id %s cancelled.",
        payload["royalty_advance_id"],
        payload["user_id"],
    )
