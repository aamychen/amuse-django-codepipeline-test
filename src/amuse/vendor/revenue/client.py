import json
import logging

import requests
from django.conf import settings

from amuse.utils import log_func
from amuse.vendor.revenue.helpers import transform_data

logger = logging.getLogger(__name__)


HEADERS = {'Content-Type': 'application/json', 'Accept': 'application/json'}
REVENUE_API_URL = settings.REVENUE_API_URL
URL_SUMMARY_BALANCE = REVENUE_API_URL + "/user/%s/balance"
URL_SUMMARY_TRANSACTIONS = REVENUE_API_URL + "/user/%s/legacy_transaction_summary"
URL_RECORD_HYPERWALLET_WITHDRAWAL = REVENUE_API_URL + "/hyperwallet_withdrawal"
URL_UPDATE_HYPERWALLET_WITHDRAWAL = REVENUE_API_URL + "/hyperwallet_withdrawal/status"
URL_RECORD_HYPERWALLET_REFUND = REVENUE_API_URL + "/hyperwallet_refund"
URL_WALLET = REVENUE_API_URL + "/user/%s/wallet_screen"


@log_func()
def get_wallet(user_id, year_month=None):
    url = URL_WALLET % user_id
    params = None
    data = None

    if year_month:
        params = {"month": year_month}

    try:
        response = requests.get(url, params=params)

        if response.status_code == 200:
            data = response.json()
        else:
            _log_revenue_call_failure(url, response)
    except Exception as e:
        _log_revenue_call_exception(url, e)

    return data


@log_func()
def get_balance(user_id):
    url = URL_SUMMARY_BALANCE % user_id
    data = None

    try:
        response = requests.get(url)

        if response.status_code == 200:
            response_dict = response.json()
            data = response_dict.get("total", None)
        else:
            _log_revenue_call_failure(url, response)
    except Exception as e:
        _log_revenue_call_exception(url, e)

    return data


@log_func()
def get_transactions(user_id):
    url = URL_SUMMARY_TRANSACTIONS % user_id
    data = {'balance': None, 'total': None, 'transactions': []}

    try:
        response = requests.get(url)

        if response.status_code == 200:
            response_dict = response.json()
            if response_dict:
                data = transform_data(response_dict)
        else:
            _log_revenue_call_failure(url, response)
    except Exception as e:
        _log_revenue_call_exception(url, e)

    if not data.get("transactions"):
        data["transactions"] = []

    return data


@log_func()
def record_withdrawal(payload, is_pending=False):
    url = URL_RECORD_HYPERWALLET_WITHDRAWAL
    data = None

    payload["total"] = str(payload["total"])
    payload["description"] = str(payload["description"]).replace("'", '"')
    payload["is_pending"] = is_pending

    payload_json = json.dumps(payload).encode("utf-8")

    logger.info(
        "record_withdrawal request with url %s payload %s headers %s",
        url,
        payload_json,
        HEADERS,
    )

    try:
        response = requests.post(url, data=payload_json, headers=HEADERS)

        if response.status_code == 200:
            data = response.json()["transaction_id"]
        else:
            _log_revenue_call_failure(url, response)
    except Exception as e:
        _log_revenue_call_exception(url, e)

    return data


@log_func()
def update_withdrawal(transaction_id, status_key, description=None):
    url = URL_UPDATE_HYPERWALLET_WITHDRAWAL
    data = None
    payload = {"transaction_id": transaction_id, status_key: True}

    if description:
        payload["description"] = str(description).replace("'", '"')

    payload_json = json.dumps(payload).encode("utf-8")

    logger.info(
        "update_withdrawal request with url %s payload %s headers %s",
        url,
        payload_json,
        HEADERS,
    )

    try:
        response = requests.put(url, data=payload_json, headers=HEADERS)

        if response.status_code == 200:
            data = response.json()["transaction_id"]
        else:
            _log_revenue_call_failure(url, response)
    except Exception as e:
        _log_revenue_call_exception(url, e)

    return data


@log_func()
def refund(user_id, revenue_transaction_id, payment_id, total, description=None):
    url = URL_RECORD_HYPERWALLET_REFUND
    data = None
    payload = {
        "user_id": user_id,
        "currency": "USD",
        "original_transaction_id": revenue_transaction_id,
        "withdrawal_reference": payment_id,
        "total": str(total),
    }

    payload_json = json.dumps(payload).encode("utf-8")

    logger.info(
        "refund request with url %s payload %s headers %s",
        url,
        payload_json,
        HEADERS,
    )

    try:
        response = requests.post(url, data=payload_json, headers=HEADERS)

        if response.status_code == 201:
            data = response.json()["transaction_id"]
        else:
            _log_revenue_call_failure(url, response)
    except Exception as e:
        _log_revenue_call_exception(url, e)

    return data


def _log_revenue_call_failure(url, response):
    logger.warning(
        "Request to %s failed with status code %s and message: %s",
        url,
        response.status_code,
        response.content,
    )


def _log_revenue_call_exception(url, e):
    logger.exception("Request to %s failed with %s", url, e)
