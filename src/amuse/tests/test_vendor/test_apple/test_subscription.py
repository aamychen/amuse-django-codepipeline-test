from datetime import datetime, timezone
from unittest.mock import Mock, patch
from uuid import uuid4

import pytest
import responses
from django.conf import settings
from requests.exceptions import ConnectionError

from amuse.vendor.apple.exceptions import (
    EmptyAppleReceiptError,
    MaxRetriesExceededError,
    UnknownAppleError,
)
from amuse.vendor.apple.subscriptions import (
    APPLE_SANDBOX_VALIDATION_URL,
    AppleReceiptValidationAPIClient,
    get_expires_date_timestamp,
    get_receipt,
    get_request_session,
    parse_auto_renew_status,
    parse_expires_date,
)
from payments.tests.factories import PaymentTransactionFactory
from subscriptions.models import Subscription
from amuse.vendor.apple.exceptions import (
    DuplicateAppleTransactionIDError,
    DuplicateAppleSubscriptionError,
)
from subscriptions.tests.factories import SubscriptionFactory
from users.tests.factories import UserFactory
from amuse.tasks import zendesk_create_or_update_user
from subscriptions.tests.vendor.apple.substring_matcher import SubstringMatcher

receipt = 'dummy data'
transaction_id = '1000000628435657'
original_transaction_id = '1000000617766328'
product_id = 'amuse_pro_monthly_renewal'
expires_date_timestamp = '1583158133000'
expires_date = datetime(2020, 3, 2, 14, 8, 53, tzinfo=timezone.utc)

request_id = str(uuid4())

ACTIVE_AND_IN_GRACE_PERIOD_STATUS_LIST = [
    Subscription.STATUS_ACTIVE,
    Subscription.STATUS_GRACE_PERIOD,
]


def mock_response(url, **kwargs):
    if 'status' not in kwargs:
        kwargs['status'] = 0

    responses.add(responses.POST, url, json=kwargs, status=200)


@pytest.fixture
def apple_receipt_validation_api_client():
    return AppleReceiptValidationAPIClient(receipt, request_id=request_id)


@patch('amuse.vendor.apple.subscriptions.get_request_session')
def test_apple_receipt_validation_api_client_initilizes_with_correct_values(
    mocked_get_request_session,
):
    apple_receipt_validation_api_client = AppleReceiptValidationAPIClient(
        receipt, request_id=request_id
    )
    assert apple_receipt_validation_api_client.url == settings.APPLE_VALIDATION_URL
    assert apple_receipt_validation_api_client.receipt == receipt
    assert apple_receipt_validation_api_client.password == settings.APPLE_KEY
    mocked_get_request_session.assert_called_once()
    assert apple_receipt_validation_api_client.session == mocked_get_request_session()
    assert apple_receipt_validation_api_client.max_retries == 3
    assert apple_receipt_validation_api_client.api_calls_count == 0
    assert apple_receipt_validation_api_client.backoff_factor == 1
    assert apple_receipt_validation_api_client.response_data is None
    assert not apple_receipt_validation_api_client.sandbox_is_called
    assert apple_receipt_validation_api_client.request_id == request_id


def test_apple_receipt_validation_api_client_initilizes_with_custom_value_for_max_retries():
    max_retries = 5
    apple_receipt_validation_api_client = AppleReceiptValidationAPIClient(
        receipt, max_retries=max_retries
    )
    assert apple_receipt_validation_api_client.max_retries == max_retries


@patch(
    'amuse.vendor.apple.subscriptions.AppleReceiptValidationAPIClient._handle_response'
)
@patch(
    'amuse.vendor.apple.subscriptions.AppleReceiptValidationAPIClient._get_apple_response'
)
def test_apple_receipt_validation_api_client_validate_receipt_succeeded(
    mocked_get_apple_response,
    mocked_handle_response,
    apple_receipt_validation_api_client,
):
    mocked_apple_response = Mock()
    mocked_get_apple_response.return_value = mocked_apple_response

    apple_receipt_validation_api_client.validate_receipt()

    mocked_get_apple_response.assert_called_once()
    mocked_handle_response.assert_called_once()


@patch('amuse.vendor.apple.subscriptions.logger')
def test_apple_receipt_validation_api_client_validate_receipt_raises_exception(
    mocked_logger, apple_receipt_validation_api_client
):
    apple_receipt_validation_api_client.api_calls_count = (
        apple_receipt_validation_api_client.max_retries
    )

    with pytest.raises(MaxRetriesExceededError):
        apple_receipt_validation_api_client.validate_receipt()
    mocked_logger.info.assert_called_once_with(
        f'Maximum retries of {apple_receipt_validation_api_client.max_retries} was'
        ' excceeded, giving up',
        extra={
            'request_id': request_id,
            'url': apple_receipt_validation_api_client.url,
        },
    )


def test_apple_receipt_validation_api_client_get_apple_response(
    apple_receipt_validation_api_client,
):
    apple_receipt_validation_api_client.session = Mock()
    payload = {
        'password': apple_receipt_validation_api_client.password,
        'receipt-data': apple_receipt_validation_api_client.receipt,
    }
    apple_receipt_validation_api_client._get_apple_response()

    assert apple_receipt_validation_api_client.api_calls_count == 1
    apple_receipt_validation_api_client.session.post.assert_called_once_with(
        apple_receipt_validation_api_client.url, json=payload
    )


@responses.activate
@patch('amuse.vendor.apple.subscriptions.AppleReceiptValidationAPIClient._retry')
def test_apple_receipt_validation_api_client_handle_response_suceeded(
    mocked_retry, apple_receipt_validation_api_client
):
    mock_response(settings.APPLE_VALIDATION_URL)

    apple_receipt_validation_api_client.validate_receipt()

    mocked_retry.assert_not_called()


@responses.activate
@patch('amuse.vendor.apple.subscriptions.AppleReceiptValidationAPIClient._retry')
def test_apple_receipt_validation_api_client_handle_response_calls_retry(
    mocked_retry, apple_receipt_validation_api_client
):
    mock_response(settings.APPLE_VALIDATION_URL, status=21199, is_retryable=True)
    apple_receipt_validation_api_client.max_retries = 1

    apple_receipt_validation_api_client.validate_receipt()

    mocked_retry.assert_called_once()


def test_apple_receipt_validation_api_client_handle_response_retry_3_times_when_connection_reset_error_is_raised(
    apple_receipt_validation_api_client,
):
    mocked_session = Mock()
    mocked_session.post.side_effect = ConnectionError('Connection error')

    apple_receipt_validation_api_client.session = mocked_session
    apple_receipt_validation_api_client.backoff_factor = 0.001
    with pytest.raises(MaxRetriesExceededError):
        apple_receipt_validation_api_client.validate_receipt()

    assert (
        mocked_session.post.call_count
        == apple_receipt_validation_api_client.max_retries
    )


@patch('amuse.vendor.apple.subscriptions.logger')
@patch('amuse.vendor.apple.subscriptions.sleep')
@patch(
    'amuse.vendor.apple.subscriptions.AppleReceiptValidationAPIClient.validate_receipt'
)
def test_apple_receipt_validation_api_client_calls_retry(
    mocked_validate_receipt,
    mocked_sleep,
    mocked_logger,
    apple_receipt_validation_api_client,
):
    old_bakoff_factor = apple_receipt_validation_api_client.backoff_factor
    apple_receipt_validation_api_client._retry()

    mocked_logger.info.assert_called_once_with(
        f'Retry calling Apple API after {old_bakoff_factor} seconds',
        extra={
            'request_id': request_id,
            'url': apple_receipt_validation_api_client.url,
        },
    )

    mocked_sleep.assert_called_once_with(old_bakoff_factor)
    assert apple_receipt_validation_api_client.backoff_factor == 2
    mocked_validate_receipt.assert_called_once()


@responses.activate
def test_apple_receipt_validation_api_client_raises_max_retries_exceeded_error(
    apple_receipt_validation_api_client,
):
    apple_receipt_validation_api_client.max_retries = 0

    with pytest.raises(MaxRetriesExceededError):
        apple_receipt_validation_api_client.validate_receipt()


@patch('amuse.vendor.apple.subscriptions.logger')
@responses.activate
def test_apple_receipt_validation_api_client_raises_unknow_apple_error(
    mocked_logger, apple_receipt_validation_api_client
):
    unknown_status = 2000
    mock_response(
        settings.APPLE_VALIDATION_URL, is_retryable=False, status=unknown_status
    )

    with pytest.raises(UnknownAppleError):
        apple_receipt_validation_api_client.validate_receipt()

    mocked_logger.error.assert_called_once_with(
        'Validate receipt failed',
        extra={
            'request_id': request_id,
            'url': apple_receipt_validation_api_client.url,
            'status': unknown_status,
        },
    )


def test_apple_receipt_validation_api_client_get_first_pending_renewal_info_succeed(
    apple_receipt_validation_api_client,
):
    first_pending_renewal_info = {'auto_renew_status': '0'}

    apple_receipt_validation_api_client.response_data = {
        'pending_renewal_info': [first_pending_renewal_info]
    }

    assert (
        apple_receipt_validation_api_client._get_first_pending_renewal_info()
        == first_pending_renewal_info
    )


@pytest.mark.parametrize(
    'sandbox_is_called,response_data,expected_status',
    [
        (False, {'pending_renewal_info': [{'auto_renew_status': '0'}]}, 0),
        (False, {'pending_renewal_info': [{'auto_renew_status': '1'}]}, 1),
        (True, {'auto_renew_status': '0'}, 0),
        (True, {'auto_renew_status': '1'}, 1),
    ],
)
def test_apple_receipt_validation_api_client_get_auto_renew_status_succeed(
    sandbox_is_called,
    response_data,
    expected_status,
    apple_receipt_validation_api_client,
):
    apple_receipt_validation_api_client.sandbox_is_called = sandbox_is_called
    apple_receipt_validation_api_client.response_data = response_data

    assert (
        apple_receipt_validation_api_client.get_auto_renew_status() == expected_status
    )


@pytest.mark.parametrize(
    'receipt,expected_status',
    [
        ({'is_in_intro_offer_period': '1'}, True),
        ({'is_in_intro_offer_period': 'true'}, True),
        ({'is_in_intro_offer_period': 'True'}, True),
        ({'is_in_intro_offer_period': True}, True),
        ({'is_in_intro_offer_period': False}, False),
        ({'is_in_intro_offer_period': '0'}, False),
        ({'is_in_intro_offer_period': 'xyz'}, False),
        ({}, False),
    ],
)
@patch('amuse.vendor.apple.subscriptions.AppleReceiptValidationAPIClient._get_receipt')
def test_apple_receipt_validation_api_client_get_is_in_intro_offer(
    mocked_get_receipt, receipt, expected_status, apple_receipt_validation_api_client
):
    mocked_get_receipt.return_value = receipt

    assert (
        apple_receipt_validation_api_client.get_is_in_intro_offer() == expected_status
    )


@patch(
    'amuse.vendor.apple.subscriptions.AppleReceiptValidationAPIClient._get_latest_receipt'
)
def test_apple_receipt_validation_api_client_get_receipt_succeed(
    mocked__get_latest_receipt, apple_receipt_validation_api_client
):
    apple_receipt_validation_api_client._get_receipt()
    mocked__get_latest_receipt.assert_called_once()


@patch('amuse.vendor.apple.subscriptions.logger')
def test_apple_receipt_validation_api_client_get_latest_receipt_raises_empty_apple_receipt_error(
    mocked_logger, apple_receipt_validation_api_client
):
    apple_receipt_validation_api_client.response_data = {}
    with pytest.raises(EmptyAppleReceiptError):
        apple_receipt_validation_api_client._get_latest_receipt()

    mocked_logger.info.assert_called_with(
        'latest_receipt_info was not found in the response',
        extra={'request_id': request_id},
    )


@pytest.mark.parametrize(
    'receipt',
    [
        {'expires_date_ms': expires_date_timestamp},
        {'expires_date': expires_date_timestamp},
    ],
)
@patch('amuse.vendor.apple.subscriptions.AppleReceiptValidationAPIClient._get_receipt')
def test_apple_receipt_validation_api_client_get_expires_date(
    mocked_get_receipt, receipt, apple_receipt_validation_api_client
):
    mocked_get_receipt.return_value = receipt

    assert apple_receipt_validation_api_client.get_expires_date() == expires_date


@pytest.mark.parametrize(
    'receipt',
    [
        {'expires_date_ms': expires_date_timestamp},
        {'expires_date': expires_date_timestamp},
    ],
)
def test_get_expires_date_timestamp(receipt):
    assert get_expires_date_timestamp(receipt) == float(expires_date_timestamp) / 1000


@patch('amuse.vendor.apple.subscriptions.logger')
@responses.activate
def test_apple_receipt_validation_api_client_succeeded(
    mocked_logger, apple_receipt_validation_api_client
):
    mock_response(settings.APPLE_VALIDATION_URL)

    apple_receipt_validation_api_client.validate_receipt()
    assert mocked_logger.info.call_count == 3
    mocked_logger.info.assert_called_with(
        'Receipt validation were successful', extra={'request_id': request_id}
    )


@patch('amuse.vendor.apple.subscriptions.Session')
def test_get_request_session(MockedSession):
    mocked_session = Mock()
    MockedSession.return_value = mocked_session
    returned_session = get_request_session()
    assert returned_session == mocked_session


def test_parse_expires_date():
    _receipt = {'expires_date': expires_date_timestamp}
    timestamp = get_expires_date_timestamp(_receipt)

    assert parse_expires_date(timestamp) == expires_date


@pytest.mark.parametrize(
    'auto_renew_status_string,auto_renew_status', [('true', True), ('false', False)]
)
def test_parse_auto_renew_status(auto_renew_status_string, auto_renew_status):
    assert parse_auto_renew_status(auto_renew_status_string) == auto_renew_status


@pytest.mark.parametrize(
    'payload,expected_receipt',
    [
        (
            {
                'notification_type': 'DID_CHANGE_RENEWAL_STATUS',
                'auto_renew_status': 'true',
                'latest_receipt_info': {
                    'expires_date_ms': expires_date_timestamp,
                    'original_transaction_id': original_transaction_id,
                    'transaction_id': transaction_id,
                    'product_id': product_id,
                },
            },
            {
                'notification_type': 'DID_CHANGE_RENEWAL_STATUS',
                'product_id': product_id,
                'transaction_id': transaction_id,
                'original_transaction_id': original_transaction_id,
                'expires_date': expires_date,
                'auto_renew_status': True,
            },
        ),
        (
            {
                'notification_type': 'DID_CHANGE_RENEWAL_STATUS',
                'auto_renew_status': 'false',
                'latest_expired_receipt_info': {
                    'expires_date_ms': expires_date_timestamp,
                    'original_transaction_id': original_transaction_id,
                    'transaction_id': transaction_id,
                    'product_id': product_id,
                },
            },
            {
                'notification_type': 'DID_CHANGE_RENEWAL_STATUS',
                'product_id': product_id,
                'transaction_id': transaction_id,
                'original_transaction_id': original_transaction_id,
                'expires_date': expires_date,
                'auto_renew_status': False,
            },
        ),
    ],
)
def test_get_receipt(payload, expected_receipt):
    assert get_receipt(payload) == expected_receipt


@pytest.mark.django_db(True)
@patch('amuse.vendor.apple.subscriptions.logger')
def test_full_payload(mock_logger, apple_receipt_validation_api_client):
    apple_receipt_validation_api_client.response_data = {
        "environment": "Production",
        "receipt": {
            "receipt_type": "Production",
            "adam_id": 1160922922,
            "app_item_id": 1160922922,
            "bundle_id": "io.amuse.ios",
            "application_version": "2913",
            "download_id": 92071437973739,
            "version_external_identifier": 840940425,
            "receipt_creation_date": "2021-03-29 08:09:39 Etc/GMT",
            "receipt_creation_date_ms": "1617005379000",
            "receipt_creation_date_pst": "2021-03-29 01:09:39 America/Los_Angeles",
            "request_date": "2021-03-29 09:41:08 Etc/GMT",
            "request_date_ms": "1617010868501",
            "request_date_pst": "2021-03-29 02:41:08 America/Los_Angeles",
            "original_purchase_date": "2021-02-02 16:17:10 Etc/GMT",
            "original_purchase_date_ms": "1612282630000",
            "original_purchase_date_pst": "2021-02-02 08:17:10 America/Los_Angeles",
            "original_application_version": "2646",
            "in_app": [
                {
                    "quantity": "1",
                    "product_id": "amuse_pro_monthly_renewal",
                    "transaction_id": "520000723529084",
                    "original_transaction_id": "520000723529084",
                    "purchase_date": "2021-02-02 17:01:26 Etc/GMT",
                    "purchase_date_ms": "1612285286000",
                    "purchase_date_pst": "2021-02-02 09:01:26 America/Los_Angeles",
                    "original_purchase_date": "2021-02-02 17:01:28 Etc/GMT",
                    "original_purchase_date_ms": "1612285288000",
                    "original_purchase_date_pst": "2021-02-02 09:01:28 America/Los_Angeles",
                    "expires_date": "2021-03-02 17:01:26 Etc/GMT",
                    "expires_date_ms": "1614704486000",
                    "expires_date_pst": "2021-03-02 09:01:26 America/Los_Angeles",
                    "web_order_line_item_id": "520000289995014",
                    "is_trial_period": "false",
                    "is_in_intro_offer_period": "false",
                    "in_app_ownership_type": "PURCHASED",
                },
                {
                    "quantity": "1",
                    "product_id": "amuse_boost_yearly_renewal_notrial",
                    "transaction_id": "520000761510694",
                    "original_transaction_id": "520000723529084",
                    "purchase_date": "2021-03-29 08:09:38 Etc/GMT",
                    "purchase_date_ms": "1617005378000",
                    "purchase_date_pst": "2021-03-29 01:09:38 America/Los_Angeles",
                    "original_purchase_date": "2021-02-02 17:01:28 Etc/GMT",
                    "original_purchase_date_ms": "1612285288000",
                    "original_purchase_date_pst": "2021-02-02 09:01:28 America/Los_Angeles",
                    "expires_date": "2022-03-29 08:09:38 Etc/GMT",
                    "expires_date_ms": "1648541378000",
                    "expires_date_pst": "2022-03-29 01:09:38 America/Los_Angeles",
                    "web_order_line_item_id": "520000289995015",
                    "is_trial_period": "false",
                    "is_in_intro_offer_period": "false",
                    "in_app_ownership_type": "PURCHASED",
                },
            ],
        },
        "latest_receipt_info": [
            {
                "quantity": "1",
                "product_id": "amuse_boost_yearly_renewal_notrial",
                "transaction_id": "520000761510694",
                "original_transaction_id": "520000723529084",
                "purchase_date": "2021-03-29 08:09:38 Etc/GMT",
                "purchase_date_ms": "1616005378000",
                "purchase_date_pst": "2021-03-29 01:09:38 America/Los_Angeles",
                "original_purchase_date": "2021-02-02 17:01:28 Etc/GMT",
                "original_purchase_date_ms": "1612285288000",
                "original_purchase_date_pst": "2021-02-02 09:01:28 America/Los_Angeles",
                "expires_date": "2022-03-29 08:09:38 Etc/GMT",
                "expires_date_ms": "1648541378000",
                "expires_date_pst": "2022-03-29 01:09:38 America/Los_Angeles",
                "web_order_line_item_id": "520000289995015",
                "is_trial_period": "false",
                "is_in_intro_offer_period": "false",
                "in_app_ownership_type": "PURCHASED",
                "subscription_group_identifier": "20581044",
            },
            {
                "quantity": "1",
                "product_id": "amuse_pro_monthly_renewal",
                "transaction_id": "520000723529084",
                "original_transaction_id": "520000723529084",
                "purchase_date": "2021-02-02 17:01:26 Etc/GMT",
                "purchase_date_ms": "1612285286000",
                "purchase_date_pst": "2021-02-02 09:01:26 America/Los_Angeles",
                "original_purchase_date": "2021-02-02 17:01:28 Etc/GMT",
                "original_purchase_date_ms": "1612285288000",
                "original_purchase_date_pst": "2021-02-02 09:01:28 America/Los_Angeles",
                "expires_date": "2021-03-02 17:01:26 Etc/GMT",
                "expires_date_ms": "1614704486000",
                "expires_date_pst": "2021-03-02 09:01:26 America/Los_Angeles",
                "web_order_line_item_id": "520000289995014",
                "is_trial_period": "false",
                "is_in_intro_offer_period": "false",
                "in_app_ownership_type": "PURCHASED",
                "subscription_group_identifier": "20581044",
            },
        ],
        "pending_renewal_info": [
            {
                "auto_renew_product_id": "amuse_boost_yearly_renewal_notrial",
                "product_id": "amuse_boost_yearly_renewal_notrial",
                "original_transaction_id": "520000723529084",
                "auto_renew_status": "1",
            }
        ],
        "status": 0,
    }

    org_txid = apple_receipt_validation_api_client.get_original_transaction_id()
    last_transaction_id = apple_receipt_validation_api_client.get_transaction_id()
    purchase_data = apple_receipt_validation_api_client.get_purchase_date()
    product_id = apple_receipt_validation_api_client.get_product_id()
    is_in_intro_offer_period = (
        apple_receipt_validation_api_client.get_is_in_intro_offer()
    )
    assert product_id == 'amuse_boost_yearly_renewal_notrial'
    assert isinstance(purchase_data, datetime)
    assert org_txid == "520000723529084"
    assert last_transaction_id == "520000761510694"
    assert apple_receipt_validation_api_client.interactive_renewal == True
    assert is_in_intro_offer_period == False

    # Simulate transaction exist case
    with patch('amuse.vendor.zendesk.api.create_or_update_user'):
        PaymentTransactionFactory(external_transaction_id="520000761510694")
        with pytest.raises(DuplicateAppleTransactionIDError):
            apple_receipt_validation_api_client.get_transaction_id()
            assert mock_logger.info.assert_called_once_with(
                SubstringMatcher(containing='AppleReceiptValidator tx exist in DB')
            )


@pytest.mark.parametrize('status', ACTIVE_AND_IN_GRACE_PERIOD_STATUS_LIST)
@pytest.mark.django_db
@patch('amuse.vendor.apple.subscriptions.logger')
@patch(
    'amuse.vendor.apple.subscriptions.AppleReceiptValidationAPIClient._get_apple_response'
)
def test_apple_receipt_validation_api_client_is_duplicate_apple_subscription_returns_true(
    mock_logger, mocked_get_response, status, apple_receipt_validation_api_client
):
    apple_receipt_validation_api_client.response_data = {
        "environment": "Production",
        "receipt": {
            "receipt_type": "Production",
            "adam_id": 1160922922,
            "app_item_id": 1160922922,
            "bundle_id": "io.amuse.ios",
            "application_version": "2913",
            "download_id": 92071437973739,
            "version_external_identifier": 840940425,
            "receipt_creation_date": "2021-03-29 08:09:39 Etc/GMT",
            "receipt_creation_date_ms": "1617005379000",
            "receipt_creation_date_pst": "2021-03-29 01:09:39 America/Los_Angeles",
            "request_date": "2021-03-29 09:41:08 Etc/GMT",
            "request_date_ms": "1617010868501",
            "request_date_pst": "2021-03-29 02:41:08 America/Los_Angeles",
            "original_purchase_date": "2021-02-02 16:17:10 Etc/GMT",
            "original_purchase_date_ms": "1612282630000",
            "original_purchase_date_pst": "2021-02-02 08:17:10 America/Los_Angeles",
            "original_application_version": "2646",
            "in_app": [
                {
                    "quantity": "1",
                    "product_id": "amuse_pro_monthly_renewal",
                    "transaction_id": "520000723529084",
                    "original_transaction_id": "520000723529084",
                    "purchase_date": "2021-02-02 17:01:26 Etc/GMT",
                    "purchase_date_ms": "1612285286000",
                    "purchase_date_pst": "2021-02-02 09:01:26 America/Los_Angeles",
                    "original_purchase_date": "2021-02-02 17:01:28 Etc/GMT",
                    "original_purchase_date_ms": "1612285288000",
                    "original_purchase_date_pst": "2021-02-02 09:01:28 America/Los_Angeles",
                    "expires_date": "2021-03-02 17:01:26 Etc/GMT",
                    "expires_date_ms": "1614704486000",
                    "expires_date_pst": "2021-03-02 09:01:26 America/Los_Angeles",
                    "web_order_line_item_id": "520000289995014",
                    "is_trial_period": "false",
                    "is_in_intro_offer_period": "false",
                    "in_app_ownership_type": "PURCHASED",
                },
                {
                    "quantity": "1",
                    "product_id": "amuse_boost_yearly_renewal_notrial",
                    "transaction_id": "520000761510694",
                    "original_transaction_id": "520000723529084",
                    "purchase_date": "2021-03-29 08:09:38 Etc/GMT",
                    "purchase_date_ms": "1617005378000",
                    "purchase_date_pst": "2021-03-29 01:09:38 America/Los_Angeles",
                    "original_purchase_date": "2021-02-02 17:01:28 Etc/GMT",
                    "original_purchase_date_ms": "1612285288000",
                    "original_purchase_date_pst": "2021-02-02 09:01:28 America/Los_Angeles",
                    "expires_date": "2022-03-29 08:09:38 Etc/GMT",
                    "expires_date_ms": "1648541378000",
                    "expires_date_pst": "2022-03-29 01:09:38 America/Los_Angeles",
                    "web_order_line_item_id": "520000289995015",
                    "is_trial_period": "false",
                    "is_in_intro_offer_period": "false",
                    "in_app_ownership_type": "PURCHASED",
                },
            ],
        },
        "latest_receipt_info": [
            {
                "quantity": "1",
                "product_id": "amuse_boost_yearly_renewal_notrial",
                "transaction_id": "520000761510694",
                "original_transaction_id": "520000723529084",
                "purchase_date": "2021-03-29 08:09:38 Etc/GMT",
                "purchase_date_ms": "1616005378000",
                "purchase_date_pst": "2021-03-29 01:09:38 America/Los_Angeles",
                "original_purchase_date": "2021-02-02 17:01:28 Etc/GMT",
                "original_purchase_date_ms": "1612285288000",
                "original_purchase_date_pst": "2021-02-02 09:01:28 America/Los_Angeles",
                "expires_date": "2022-03-29 08:09:38 Etc/GMT",
                "expires_date_ms": "1648541378000",
                "expires_date_pst": "2022-03-29 01:09:38 America/Los_Angeles",
                "web_order_line_item_id": "520000289995015",
                "is_trial_period": "false",
                "is_in_intro_offer_period": "false",
                "in_app_ownership_type": "PURCHASED",
                "subscription_group_identifier": "20581044",
            },
            {
                "quantity": "1",
                "product_id": "amuse_pro_monthly_renewal",
                "transaction_id": "520000723529084",
                "original_transaction_id": "520000723529084",
                "purchase_date": "2021-02-02 17:01:26 Etc/GMT",
                "purchase_date_ms": "1612285286000",
                "purchase_date_pst": "2021-02-02 09:01:26 America/Los_Angeles",
                "original_purchase_date": "2021-02-02 17:01:28 Etc/GMT",
                "original_purchase_date_ms": "1612285288000",
                "original_purchase_date_pst": "2021-02-02 09:01:28 America/Los_Angeles",
                "expires_date": "2021-03-02 17:01:26 Etc/GMT",
                "expires_date_ms": "1614704486000",
                "expires_date_pst": "2021-03-02 09:01:26 America/Los_Angeles",
                "web_order_line_item_id": "520000289995014",
                "is_trial_period": "false",
                "is_in_intro_offer_period": "false",
                "in_app_ownership_type": "PURCHASED",
                "subscription_group_identifier": "20581044",
            },
        ],
        "pending_renewal_info": [
            {
                "auto_renew_product_id": "amuse_boost_yearly_renewal_notrial",
                "product_id": "amuse_boost_yearly_renewal_notrial",
                "original_transaction_id": "520000723529084",
                "auto_renew_status": "1",
            }
        ],
        "status": 0,
    }

    mocked_get_response.return_value = apple_receipt_validation_api_client.response_data
    validate_simple = apple_receipt_validation_api_client.validate_simple()
    assert validate_simple == True

    with patch('amuse.vendor.zendesk.api.create_or_update_user'):
        user = UserFactory()
        user_2 = UserFactory()

        SubscriptionFactory(
            user=user_2,
            status=status,
            payment_method__external_recurring_id='520000723529084',
            payment_method__method='AAPL',
        )
        with pytest.raises(DuplicateAppleSubscriptionError):
            apple_receipt_validation_api_client.get_original_transaction_id(user)
            assert mock_logger.warrning.assert_called_once_with(
                SubstringMatcher(containing='Active subscription with orig_txid')
            )

        assert apple_receipt_validation_api_client._is_duplicate_apple_subscription(
            '520000723529084', user
        )


@pytest.mark.parametrize(
    "expected, is_trial_period, is_in_intro_offer_period",
    [
        (False, 'true', 'true'),
        (False, 'true', 'false'),
        (False, 'false', 'true'),
        (True, 'false', 'false'),
    ],
)
def test_is_introductory_offer_eligible(
    expected,
    is_trial_period,
    is_in_intro_offer_period,
    apple_receipt_validation_api_client,
):
    apple_receipt_validation_api_client.response_data = {
        "environment": "Production",
        "receipt": {},
        "latest_receipt_info": [
            {"is_trial_period": 'false', "is_in_intro_offer_period": 'false'},
            {
                "is_trial_period": is_trial_period,
                "is_in_intro_offer_period": is_in_intro_offer_period,
            },
        ],
        "pending_renewal_info": [],
        "status": 0,
    }

    actual = apple_receipt_validation_api_client.is_introductory_offer_eligible()
    assert expected == actual
