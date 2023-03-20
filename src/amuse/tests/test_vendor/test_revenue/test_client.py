import json

import responses

from amuse.tests.test_vendor.test_revenue.helpers import mock_transaction_summary
from amuse.vendor.revenue.client import (
    get_balance,
    get_transactions,
    record_withdrawal,
    update_withdrawal,
    URL_RECORD_HYPERWALLET_WITHDRAWAL,
    URL_SUMMARY_BALANCE,
    URL_SUMMARY_TRANSACTIONS,
    URL_UPDATE_HYPERWALLET_WITHDRAWAL,
)
from amuse.vendor.revenue.helpers import transform_data


@responses.activate
def test_get_summary_balance_success_returns_results():
    response = {"total": 123.123}

    responses.add(
        responses.GET, URL_SUMMARY_BALANCE % 111, json.dumps(response), status=200
    )

    assert get_balance(user_id=111) == response["total"]


@responses.activate
def test_get_summary_balance_returns_none_when_call_fails():
    responses.add(responses.GET, URL_SUMMARY_BALANCE % 111, status=400)

    assert get_balance(user_id=111) is None


@responses.activate
def test_get_summary_transactions_success_returns_results():
    result = transform_data(json.loads(mock_transaction_summary))

    responses.add(
        responses.GET,
        URL_SUMMARY_TRANSACTIONS % 111,
        mock_transaction_summary,
        status=200,
    )

    assert get_transactions(user_id=111) == result


@responses.activate
def test_get_summary_transactions_returns_none_when_call_fails():
    responses.add(responses.GET, URL_SUMMARY_TRANSACTIONS % 111, status=400)
    mock_response = {'balance': None, 'total': None, 'transactions': []}

    assert get_transactions(user_id=111) == mock_response


@responses.activate
def test_get_summary_transactions_returns_none_when_exception():
    mock_response = {'balance': None, 'total': None, 'transactions': []}

    assert get_transactions(user_id='xxx') == mock_response


@responses.activate
def test_get_summary_transactions_handles_revenue_system_zero_balance_response():
    responses.add(
        responses.GET,
        URL_SUMMARY_TRANSACTIONS % 111,
        json.dumps({'balance': None, 'total': None}),
        status=200,
    )
    mock_response = {'balance': None, 'total': None, 'transactions': []}

    assert get_transactions(user_id=111) == mock_response


@responses.activate
def test_record_hyperwallet_withdrawal_success():
    payload = {"user_id": 111, "total": "10.00", "currency": "USD", "description": {}}
    response = {"transaction_id": "6e570b62-7f8d-41ee-8b99-e611d9f3626d"}

    responses.add(
        responses.POST,
        URL_RECORD_HYPERWALLET_WITHDRAWAL,
        json.dumps(response),
        status=200,
    )

    assert record_withdrawal(payload, is_pending=True) == response["transaction_id"]


@responses.activate
def test_record_hyperwallet_withdrawal_returns_none_when_call_fails():
    payload = {"user_id": 111, "total": "10.00", "currency": "USD", "description": {}}

    responses.add(responses.POST, URL_RECORD_HYPERWALLET_WITHDRAWAL, status=400)

    assert record_withdrawal(payload, is_pending=True) is None


@responses.activate
def test_update_pending_hyperwallet_withdrawal_to_complete_success():
    response = {"transaction_id": "6e570b62-7f8d-41ee-8b99-e611d9f3626d"}

    responses.add(
        responses.PUT,
        URL_UPDATE_HYPERWALLET_WITHDRAWAL,
        json.dumps(response),
        status=200,
    )

    assert (
        update_withdrawal(
            response["transaction_id"], status_key="is_complete", description={}
        )
        == response["transaction_id"]
    )


@responses.activate
def test_update_pending_hyperwallet_withdrawal_to_cancelled_success():
    response = {"transaction_id": "6e570b62-7f8d-41ee-8b99-e611d9f3626d"}

    responses.add(
        responses.PUT,
        URL_UPDATE_HYPERWALLET_WITHDRAWAL,
        json.dumps(response),
        status=200,
    )

    assert (
        update_withdrawal(
            response["transaction_id"], status_key="is_cancelled", description={}
        )
        == response["transaction_id"]
    )


@responses.activate
def test_update_pending_hyperwallet_withdrawal_returns_none_when_call_fails():
    responses.add(responses.PUT, URL_UPDATE_HYPERWALLET_WITHDRAWAL, status=400)

    assert (
        update_withdrawal(
            transaction_id="xxx", status_key="is_cancelled", description={}
        )
        is None
    )
