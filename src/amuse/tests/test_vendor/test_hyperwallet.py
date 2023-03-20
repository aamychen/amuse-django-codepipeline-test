import json
import pytest
import responses

from decimal import Decimal
from unittest import mock
from rest_framework.serializers import ValidationError
from rest_framework.test import APIRequestFactory

from waffle.models import Flag

from django.conf import settings
from django.http import HttpRequest
from django.test import TransactionTestCase, override_settings

from amuse.vendor.hyperwallet.client import (
    create,
    create_payment,
    create_user,
    get_payment_payload,
    get_payments,
    get_program_token,
    get_user_payload,
    check_account_exists,
    post_process_standard_withdrawal,
    cancel_standard_withdrawal,
    post_process_royalty_advance,
    cancel_royalty_advance,
)
from amuse.vendor.hyperwallet.exceptions import (
    HyperwalletAPIError,
    LimitSubceededError,
    FirstNameConstraintError,
    LastNameConstraintError,
    IncorrectFundingProgramError,
    InvalidWalletStatusError,
    StoreInvalidCurrencyError,
    DuplicateExtraIdTypeError,
    LIMIT_SUBCEEDED_MSG,
    NAME_CONSTRAINT_MSG,
    INCORRECT_FUNDING_PROGRAM_MSG,
    INVALID_WALLET_STATUS_MSG,
    STORE_INVALID_CURRENCY_MSG,
    DUPLICATE_EXTRA_ID_TYPE_MSG,
    GENERIC_ERROR_MSG,
)
from amuse.vendor.hyperwallet.helpers import (
    is_amount_within_limit,
    check_hyperwallet_is_active,
    hyperwallet_validate_email,
)
from slayer.exceptions import (
    RoyaltyAdvanceCancelError,
    RoyaltyAdvanceActivateError,
)
from amuse.tests.helpers import (
    ZENDESK_MOCK_API_URL_TOKEN,
    hyperwallet_mock_response_create_user,
    hyperwallet_mock_response_create_payment,
    hyperwallet_mock_payload_create_payment,
    hyperwallet_mock_response_error,
    mock_limit_subceeded_response,
    mock_firstname_constraint_response,
    mock_lastname_constraint_response,
    mock_incorrect_funding_program_response,
    mock_invalid_wallet_status_response,
    mock_store_invalid_currency_response,
    mock_duplicate_extra_id_type_response,
    mock_unknown_error_response,
)
from releases.models import RoyaltySplit
from releases.tests.factories import RoyaltySplitFactory
from users.models import User, UserMetadata
from users.tests.factories import UserFactory


@override_settings(
    HYPERWALLET_ENDPOINT="https://hyperwallet.amuse.io",
    HYPERWALLET_USER="rest-user",
    HYPERWALLET_PASSWORD="rest-pass",
    HYPERWALLET_PROGRAM_TOKEN_SE="program-sweden",
    HYPERWALLET_PROGRAM_TOKEN_REST_OF_WORLD="program-rest-of-world",
    HYPERWALLET_PROGRAM_TOKEN_EU="program-eu",
    **ZENDESK_MOCK_API_URL_TOKEN,
)
class HyperwalletTestCase(TransactionTestCase):
    @responses.activate
    @mock.patch("amuse.tasks.zendesk_create_or_update_user")
    def setUp(self, mock_zendesk):
        self.user = UserFactory(country="SE", phone="0704554090")
        self.user2 = UserFactory(country="US", phone="+1-202-555-0168")
        self.user3 = UserFactory(country="FR", phone="+33 785 5515 51")

        self.transaction_id_1 = "transaction_id_se"
        self.transaction_id_2 = "transaction_id_row"
        self.transaction_id_3 = "transaction_id_eu"

        self.user_token = "usr-f9154016-94e8-4686-a840-075688ac07b5"
        self.user_token2 = "usr-b9154016-94e8-4686-a840-075688ac07b5"
        self.user_token3 = "usr-56896dd7-3fc6-447e-b19a-3541ae4564f2"

        program_token_se = settings.HYPERWALLET_PROGRAM_TOKEN_SE
        program_token_rest_of_world = settings.HYPERWALLET_PROGRAM_TOKEN_REST_OF_WORLD
        program_token_eu = settings.HYPERWALLET_PROGRAM_TOKEN_EU

        self.response_create_payment = hyperwallet_mock_response_create_payment(
            self.user_token, self.transaction_id_1, program_token_se
        )
        self.response_create_payment2 = hyperwallet_mock_response_create_payment(
            self.user_token2, self.transaction_id_2, program_token_rest_of_world
        )
        self.response_create_payment3 = hyperwallet_mock_response_create_payment(
            self.user_token3, self.transaction_id_3, program_token_eu
        )
        self.response_create_user = hyperwallet_mock_response_create_user(
            self.user, self.user_token, program_token_se
        )
        self.response_create_user2 = hyperwallet_mock_response_create_user(
            self.user2, self.user_token2, program_token_rest_of_world
        )
        self.response_create_user3 = hyperwallet_mock_response_create_user(
            self.user3, self.user_token3, program_token_eu
        )
        self.payload_create_payment = hyperwallet_mock_payload_create_payment(
            self.user_token, self.transaction_id_1, program_token_se
        )

    @responses.activate
    @mock.patch("amuse.vendor.hyperwallet.client.cancel_standard_withdrawal")
    @mock.patch("amuse.vendor.hyperwallet.client.get_user_payload")
    def test_create_user_raises_error(
        self, mock_get_user_payload, mock_cancel_standard_withdrawal
    ):
        mock_get_user_payload.return_value = None
        responses.add(
            responses.POST,
            '%s/users' % settings.HYPERWALLET_ENDPOINT,
            json.dumps(hyperwallet_mock_response_error()),
            status=400,
        )

        with pytest.raises(HyperwalletAPIError):
            create_user({"is_valid_royalty_advance": False})

    @mock.patch("amuse.vendor.hyperwallet.client.get_payment_payload")
    @mock.patch("amuse.vendor.hyperwallet.client.create")
    def test_create_payment_raises_error(self, mock_create, mock_get_payment_payload):
        mock_get_payment_payload.return_value = None
        mock_create.side_effect = HyperwalletAPIError

        with self.assertRaises(HyperwalletAPIError):
            create_payment(
                payload={
                    "user_id": 1,
                    "transaction_id": "xxx",
                    "amount": Decimal("10.0"),
                    "description": None,
                }
            )

    @mock.patch("amuse.vendor.hyperwallet.client.get")
    def test_check_acount_exists_raises_error(self, mock_get):
        mock_get.side_effect = HyperwalletAPIError

        with self.assertRaises(HyperwalletAPIError):
            check_account_exists(email="user@amuse.io")

    @responses.activate
    @mock.patch("amuse.vendor.hyperwallet.client.update_withdrawal")
    def test_create_user_and_payment_sweden(self, mock_update_withdrawal):
        payee_email = "the.email.we.want@amuse.io"
        responses.add(
            responses.POST,
            '%s/users' % settings.HYPERWALLET_ENDPOINT,
            json.dumps(self.response_create_user),
            status=201,
        )
        responses.add(
            responses.POST,
            '%s/payments' % settings.HYPERWALLET_ENDPOINT,
            json.dumps(self.response_create_payment),
            status=201,
        )

        payload = {
            "hyperwallet_user_token": None,
            "transaction_id": "xxx",
            "user_id": self.user.id,
            "user_validated_phone": "+46704554090",
            "email": payee_email,
            "amount": Decimal("18.99"),
            "description": {},
        }

        create_user(payload)
        create_payment(payload)

        assert len(responses.calls) == 2
        mock_update_withdrawal.assert_called_once()

        request_body = json.loads(responses.calls[0].request.body)
        assert request_body["programToken"] == settings.HYPERWALLET_PROGRAM_TOKEN_SE
        assert request_body["email"] == payee_email

    @responses.activate
    @mock.patch("amuse.vendor.hyperwallet.client.update_withdrawal")
    def test_create_user_and_payment_rest_of_world(self, mock_update_withdrawal):
        payee_email = "the.email.we.want@amuse.io"

        responses.add(
            responses.POST,
            '%s/users' % settings.HYPERWALLET_ENDPOINT,
            json.dumps(self.response_create_user2),
            status=201,
        )
        responses.add(
            responses.POST,
            '%s/payments' % settings.HYPERWALLET_ENDPOINT,
            json.dumps(self.response_create_payment2),
            status=201,
        )

        payload = {
            "hyperwallet_user_token": None,
            "transaction_id": "xxx",
            "user_id": self.user2.id,
            "user_validated_phone": "+46704554090",
            "email": payee_email,
            "amount": Decimal("18.99"),
        }

        create_user(payload)
        payload["description"] = {"hyperwallet_payment_token": "xxx"}
        create_payment(payload)

        assert len(responses.calls) == 2

        request_body = json.loads(responses.calls[0].request.body)
        assert (
            request_body["programToken"]
            == settings.HYPERWALLET_PROGRAM_TOKEN_REST_OF_WORLD
        )
        assert request_body["email"] == payee_email

    @responses.activate
    @mock.patch("amuse.vendor.hyperwallet.client.update_withdrawal")
    def test_create_user_and_payment_eu(self, mock_update_withdrawal):
        payee_email = "the.email.we.want@amuse.io"
        responses.add(
            responses.POST,
            '%s/users' % settings.HYPERWALLET_ENDPOINT,
            json.dumps(self.response_create_user3),
            status=201,
        )
        responses.add(
            responses.POST,
            '%s/payments' % settings.HYPERWALLET_ENDPOINT,
            json.dumps(self.response_create_payment2),
            status=201,
        )

        payload = {
            "hyperwallet_user_token": None,
            "transaction_id": "xxx",
            "user_id": self.user3.id,
            "user_validated_phone": "+46704554090",
            "email": payee_email,
            "amount": Decimal("18.99"),
        }

        create_user(payload)
        payload["description"] = {"hyperwallet_payment_token": "xxx"}
        create_payment(payload)

        assert len(responses.calls) == 2

        mock_update_withdrawal.assert_called_once()

        request_body = json.loads(responses.calls[0].request.body)
        assert request_body["email"] == payee_email

    @responses.activate
    def test_create_payment_sweden(self):
        responses.add(
            responses.POST,
            '%s/payments' % settings.HYPERWALLET_ENDPOINT,
            json.dumps(self.response_create_payment),
            status=201,
        )

        payload = {
            "hyperwallet_user_token": self.user_token,
            "transaction_id": "xxx",
            "user_id": self.user.id,
            "user_validated_phone": None,
            "amount": Decimal("18.99"),
            "description": {"hyperwallet_payment_token": "xxx"},
        }

        create_payment(payload)

        assert len(responses.calls) == 2

        program_token = json.loads(responses.calls[0].request.body)["programToken"]
        assert program_token == settings.HYPERWALLET_PROGRAM_TOKEN_SE

    @responses.activate
    @mock.patch("amuse.vendor.hyperwallet.client.post_process_standard_withdrawal")
    def test_create_payment_success_retains_payload_structure(self, mock_post_process):
        responses.add(
            responses.POST,
            '%s/payments' % settings.HYPERWALLET_ENDPOINT,
            json.dumps(self.response_create_payment),
            status=201,
        )

        payload = {
            "hyperwallet_user_token": self.user_token,
            "transaction_id": "xxx",
            "user_id": self.user.id,
            "user_validated_phone": "+46704554090",
            "amount": Decimal("18.99"),
            "description": {"data_from_view": "blabla"},
        }

        create_payment(payload)

        mock_post_process.assert_called_once_with(payload)

    @responses.activate
    @mock.patch("amuse.vendor.hyperwallet.client.cancel_standard_withdrawal")
    def test_create_payment_failure_retains_payload_structure(self, mock_cancel):
        responses.add(
            responses.POST,
            '%s/payments' % settings.HYPERWALLET_ENDPOINT,
            json=mock_incorrect_funding_program_response,
            status=400,
        )

        payload = {
            "transaction_id": "xxx",
            "hyperwallet_user_token": self.user_token,
            "user_id": self.user.id,
            "user_validated_phone": "+46704554090",
            "amount": Decimal("18.99"),
            "description": {"data_from_view": "blabla"},
        }

        with pytest.raises(IncorrectFundingProgramError):
            create_payment(payload)

        mock_cancel.assert_called_once_with(payload)

    @responses.activate
    def test_create_payment_rest_of_world(self):
        responses.add(
            responses.POST,
            '%s/payments' % settings.HYPERWALLET_ENDPOINT,
            json.dumps(self.response_create_payment2),
            status=201,
        )

        payload = {
            "transaction_id": "xxx",
            "hyperwallet_user_token": self.user_token2,
            "user_id": self.user2.id,
            "user_validated_phone": "+46704554090",
            "amount": Decimal("18.99"),
            "description": {"hyperwallet_payment_token": "xxx"},
        }

        create_payment(payload)

        assert len(responses.calls) == 2

        program_token = json.loads(responses.calls[0].request.body)["programToken"]
        assert program_token == settings.HYPERWALLET_PROGRAM_TOKEN_REST_OF_WORLD

    @responses.activate
    def test_create_payment_eu(self):
        responses.add(
            responses.POST,
            '%s/payments' % settings.HYPERWALLET_ENDPOINT,
            json.dumps(self.response_create_payment3),
            status=201,
        )

        payload = {
            "transaction_id": "xxx",
            "hyperwallet_user_token": self.user_token3,
            "user_id": self.user3.id,
            "user_validated_phone": "+46704554090",
            "amount": Decimal("18.99"),
            "description": {"hyperwallet_payment_token": "xxx"},
        }

        create_payment(payload)

        assert len(responses.calls) == 2

        program_token = json.loads(responses.calls[0].request.body)["programToken"]
        assert program_token == settings.HYPERWALLET_PROGRAM_TOKEN_EU

    @responses.activate
    @mock.patch("amuse.vendor.hyperwallet.client.cancel_standard_withdrawal")
    @mock.patch("amuse.vendor.hyperwallet.client.get_user_payload")
    def test_create_error_raises_exception(
        self, mock_get_user_payload, mock_cancel_standard_withdrawal
    ):
        mock_get_user_payload.return_value = None
        responses.add(
            responses.POST,
            '%s/users' % settings.HYPERWALLET_ENDPOINT,
            json.dumps(hyperwallet_mock_response_error()),
            status=400,
        )

        with pytest.raises(HyperwalletAPIError):
            create_user({"is_valid_royalty_advance": False})

        assert len(responses.calls) == 1
        mock_cancel_standard_withdrawal.assert_called_once()

    @responses.activate
    @mock.patch("amuse.vendor.hyperwallet.client.cancel_standard_withdrawal")
    @mock.patch("amuse.vendor.hyperwallet.client.get_payment_payload")
    def test_create_raises_limit_subceeded_error(
        self, mock_get_payment_payload, mock_cancel_standard_withdrawal
    ):
        mock_get_payment_payload.return_value = None
        responses.add(
            responses.POST,
            '%s/payments' % settings.HYPERWALLET_ENDPOINT,
            json=mock_limit_subceeded_response,
            status=400,
        )
        with pytest.raises(LimitSubceededError) as e:
            create_payment({"is_valid_royalty_advance": False})

        assert e.value.error_message == LIMIT_SUBCEEDED_MSG
        mock_cancel_standard_withdrawal.assert_called_once()

    @responses.activate
    @mock.patch("amuse.vendor.hyperwallet.client.cancel_standard_withdrawal")
    @mock.patch("amuse.vendor.hyperwallet.client.get_payment_payload")
    def test_create_raises_incorrect_funding_program_error(
        self, mock_get_payment_payload, mock_cancel_standard_withdrawal
    ):
        mock_get_payment_payload.return_value = None
        responses.add(
            responses.POST,
            '%s/payments' % settings.HYPERWALLET_ENDPOINT,
            json=mock_incorrect_funding_program_response,
            status=400,
        )
        with pytest.raises(IncorrectFundingProgramError) as e:
            create_payment({"is_valid_royalty_advance": False})

        assert e.value.error_message == INCORRECT_FUNDING_PROGRAM_MSG
        mock_cancel_standard_withdrawal.assert_called_once()

    @responses.activate
    @mock.patch("amuse.vendor.hyperwallet.client.cancel_standard_withdrawal")
    @mock.patch("amuse.vendor.hyperwallet.client.get_payment_payload")
    def test_create_raises_invalid_wallet_status_error(
        self, mock_get_payment_payload, mock_cancel_standard_withdrawal
    ):
        mock_get_payment_payload.return_value = None
        responses.add(
            responses.POST,
            '%s/payments' % settings.HYPERWALLET_ENDPOINT,
            json=mock_invalid_wallet_status_response,
            status=400,
        )
        with pytest.raises(InvalidWalletStatusError) as e:
            create_payment({"is_valid_royalty_advance": False})

        assert e.value.error_message == INVALID_WALLET_STATUS_MSG
        mock_cancel_standard_withdrawal.assert_called_once()

    @responses.activate
    @mock.patch("amuse.vendor.hyperwallet.client.cancel_standard_withdrawal")
    @mock.patch("amuse.vendor.hyperwallet.client.get_payment_payload")
    def test_create_raises_store_invalid_currency_error(
        self, mock_get_payment_payload, mock_cancel_standard_withdrawal
    ):
        mock_get_payment_payload.return_value = None
        responses.add(
            responses.POST,
            '%s/payments' % settings.HYPERWALLET_ENDPOINT,
            json=mock_store_invalid_currency_response,
            status=400,
        )
        with pytest.raises(StoreInvalidCurrencyError) as e:
            create_payment({"is_valid_royalty_advance": False})

        assert e.value.error_message == STORE_INVALID_CURRENCY_MSG
        mock_cancel_standard_withdrawal.assert_called_once()

    @responses.activate
    @mock.patch("amuse.vendor.hyperwallet.client.cancel_standard_withdrawal")
    @mock.patch("amuse.vendor.hyperwallet.client.get_user_payload")
    def test_create_raises_firstname_constraint_error(
        self, mock_get_user_payload, mock_cancel_standard_withdrawal
    ):
        mock_get_user_payload.return_value = None
        responses.add(
            responses.POST,
            '%s/users' % settings.HYPERWALLET_ENDPOINT,
            json=mock_firstname_constraint_response,
            status=400,
        )
        with pytest.raises(FirstNameConstraintError) as e:
            create_user({"is_valid_royalty_advance": False})

        assert e.value.error_message == NAME_CONSTRAINT_MSG % "first"
        mock_cancel_standard_withdrawal.assert_called_once()

    @responses.activate
    @mock.patch("amuse.vendor.hyperwallet.client.cancel_standard_withdrawal")
    @mock.patch("amuse.vendor.hyperwallet.client.get_user_payload")
    def test_create_raises_lastname_constraint_error(
        self, mock_get_user_payload, mock_cancel_standard_withdrawal
    ):
        mock_get_user_payload.return_value = None
        responses.add(
            responses.POST,
            '%s/users' % settings.HYPERWALLET_ENDPOINT,
            json=mock_lastname_constraint_response,
            status=400,
        )
        with pytest.raises(LastNameConstraintError) as e:
            create_user({"is_valid_royalty_advance": False})

        assert e.value.error_message == NAME_CONSTRAINT_MSG % "last"
        mock_cancel_standard_withdrawal.assert_called_once()

    @responses.activate
    @mock.patch("amuse.vendor.hyperwallet.client.cancel_standard_withdrawal")
    @mock.patch("amuse.vendor.hyperwallet.client.get_user_payload")
    def test_create_raises_duplicate_extra_id_type_error(
        self, mock_get_user_payload, mock_cancel_standard_withdrawal
    ):
        mock_get_user_payload.return_value = None
        responses.add(
            responses.POST,
            '%s/users' % settings.HYPERWALLET_ENDPOINT,
            json=mock_duplicate_extra_id_type_response,
            status=400,
        )
        with pytest.raises(DuplicateExtraIdTypeError) as e:
            create_user({"is_valid_royalty_advance": False})

        assert e.value.error_message == DUPLICATE_EXTRA_ID_TYPE_MSG
        mock_cancel_standard_withdrawal.assert_called_once()

    @responses.activate
    @mock.patch("amuse.vendor.hyperwallet.client.cancel_standard_withdrawal")
    @mock.patch("amuse.vendor.hyperwallet.client.get_user_payload")
    def test_create_raises_generic_hyperwallet_error(
        self, mock_get_user_payload, mock_cancel_standard_withdrawal
    ):
        mock_get_user_payload.return_value = None
        responses.add(
            responses.POST,
            '%s/users' % settings.HYPERWALLET_ENDPOINT,
            json=mock_unknown_error_response,
            status=400,
        )
        with pytest.raises(HyperwalletAPIError) as e:
            create_user({"is_valid_royalty_advance": False})

        assert e.value.error_message == GENERIC_ERROR_MSG
        mock_cancel_standard_withdrawal.assert_called_once()

    def test_create_unallowed_endpoint_raises_exception(self):
        with pytest.raises(AssertionError):
            create("i-want-free-money", self.payload_create_payment)

    def test_get_payment_payload_converts_to_positive_rounded_amount(self):
        amount = Decimal("18.94")
        payload = get_payment_payload(
            {
                "user_id": self.user.id,
                "transaction_id": self.transaction_id_1,
                "amount": amount,
                "hyperwallet_user_token": "xxx",
            }
        )

        assert payload["amount"] == str(amount)

    def test_get_program_token_returns_correct_token(self):
        assert get_program_token("SE") == settings.HYPERWALLET_PROGRAM_TOKEN_SE
        assert get_program_token("DE") == settings.HYPERWALLET_PROGRAM_TOKEN_EU
        assert (
            get_program_token("US") == settings.HYPERWALLET_PROGRAM_TOKEN_REST_OF_WORLD
        )

    def test_get_user_payload_uses_withdrawal_email_address(self):
        payee_email = "the.email.we.want@amuse.io"
        self.user.email = "not.the.email.we.want@amuse.io"
        self.user.save()
        self.user.refresh_from_db()

        user_payload = get_user_payload(
            {
                "user_id": self.user.id,
                "transaction_id": self.transaction_id_1,
                "user_validated_phone": "+46704554090",
                "email": payee_email,
            }
        )
        assert user_payload['email'] == payee_email

    @mock.patch("amuse.vendor.hyperwallet.client.post_process_royalty_advance")
    @mock.patch("amuse.vendor.hyperwallet.client.create")
    def test_create_payment_royalty_advance_success(
        self, mock_create, mock_post_process_royalty_advance
    ):
        payload = {
            "transaction_id": "xxx",
            "user_id": self.user.id,
            "amount": Decimal("89.99"),
            "hyperwallet_user_token": "hwhwhw",
            "royalty_advance_offer_id": "xxx-xxx",
            "is_valid_royalty_advance": True,
            "description": {"info_from_view": "blabla"},
        }
        create_payment(payload)

        mock_post_process_royalty_advance.assert_called_once()

    @mock.patch("amuse.vendor.hyperwallet.client.cancel_royalty_advance")
    @mock.patch("amuse.vendor.hyperwallet.client.create")
    def test_create_payment_royalty_advance_failure(
        self, mock_create, mock_cancel_royalty_advance
    ):
        mock_create.side_effect = HyperwalletAPIError
        payload = {
            "transaction_id": "xxx",
            "user_id": self.user.id,
            "amount": Decimal("89.99"),
            "hyperwallet_user_token": "hwhwhw",
            "royalty_advance_offer_id": "xxx-xxx",
            "is_valid_royalty_advance": True,
        }

        with self.assertRaises(HyperwalletAPIError):
            create_payment(payload)

        mock_cancel_royalty_advance.assert_called_once()

    def test_get_user_payload_returns_postal_code(self):
        postal_code = "123456"
        payee_email = "the.email.we.want@amuse.io"
        self.user.email = "not.the.email.we.want@amuse.io"
        self.user.save()
        self.user.refresh_from_db()

        user_payload = get_user_payload(
            {
                "user_id": self.user.id,
                "transaction_id": self.transaction_id_1,
                "user_validated_phone": "+46704554090",
                "email": payee_email,
                "postal_code": postal_code,
            }
        )
        assert user_payload['postalCode'] == postal_code


@override_settings(
    HYPERWALLET_ENDPOINT="https://hyperwallet.amuse.io",
    HYPERWALLET_USER="rest-user",
    HYPERWALLET_PASSWORD="rest-pass",
    HYPERWALLET_PROGRAM_TOKEN_SE="program-sweden",
    HYPERWALLET_PROGRAM_TOKEN_REST_OF_WORLD="program-rest-of-world",
    HYPERWALLET_PROGRAM_TOKEN_EU="program-eu",
    HYPERWALLET_MIN_WITHDRAWAL_LIMIT=Decimal("10.00"),
    HYPERWALLET_MAX_WITHDRAWAL_LIMIT=Decimal("10000.00"),
    **ZENDESK_MOCK_API_URL_TOKEN,
)
class HyperwalletHelpersTestCase(TransactionTestCase):
    @responses.activate
    @mock.patch("amuse.tasks.zendesk_create_or_update_user")
    def setUp(self, mock_zendesk):
        self.user = UserFactory(email="original.user.email@amuse.io")
        self.user_meta_data = UserMetadata.objects.create(
            user=self.user, hyperwallet_user_token="the-best-token"
        )

        django_request = HttpRequest()
        factory = APIRequestFactory()
        self.request = factory.post('/users/withdrawal/', {})
        self.request._request = django_request
        self.request.user = self.user
        self.request._request.user = self.user

    def tearDown(self):
        Flag.objects.all().delete()

    def test_is_amount_within_limit_detects_within_limit(self):
        assert is_amount_within_limit(
            self.request._request, Decimal("500.00"), is_valid_royalty_advance=False
        )

    def test_is_amount_within_limit_detects_under_limit(self):
        assert not is_amount_within_limit(
            self.request._request, Decimal("5.00"), is_valid_royalty_advance=False
        )

    def test_is_amount_within_limit_detects_over_limit(self):
        assert not is_amount_within_limit(
            self.request._request, Decimal("50000.00"), is_valid_royalty_advance=False
        )

    def test_is_amount_within_limit_detects_verified_users_limit(self):
        flag = Flag.objects.create(name="vendor:hyperwallet:override-max-limit")
        flag.users.set([self.user.id])
        flag.save()
        assert is_amount_within_limit(
            self.request._request, Decimal("19000.00"), is_valid_royalty_advance=False
        )

    def test_is_amount_within_limit_detects_advance_within_limit(self):
        assert is_amount_within_limit(
            self.request._request, Decimal("29500.00"), is_valid_royalty_advance=True
        )

    def test_check_hyperwallet_is_active_detects_flag_is_active_and_amount_within_is_limit(
        self,
    ):
        positive_amount = Decimal('100.00')
        Flag.objects.create(name='vendor:hyperwallet', everyone=True)

        is_active = check_hyperwallet_is_active(
            self.request, positive_amount, is_valid_royalty_advance=False
        )

        assert is_active

    def test_check_hyperwallet_is_active_detects_flag_is_inactive_and_amount_within_is_limit(
        self,
    ):
        positive_amount = Decimal('100.00')
        Flag.objects.create(name='vendor:hyperwallet', everyone=False)

        is_active = check_hyperwallet_is_active(
            self.request, positive_amount, is_valid_royalty_advance=False
        )

        assert not is_active

    def test_check_hyperwallet_is_active_detects_flag_is_active_and_amount_not_within_limit(
        self,
    ):
        positive_amount = Decimal('1000000.00')
        Flag.objects.create(name='vendor:hyperwallet', everyone=True)

        is_active = check_hyperwallet_is_active(
            self.request, positive_amount, is_valid_royalty_advance=False
        )

        assert not is_active

    def test_check_hyperwallet_is_active_detects_flag_is_inactive_and_amount_not_within_limit(
        self,
    ):
        positive_amount = Decimal('1000000.00')
        Flag.objects.create(name='vendor:hyperwallet', everyone=False)

        is_active = check_hyperwallet_is_active(
            self.request, positive_amount, is_valid_royalty_advance=False
        )

        assert not is_active

    def test_check_hyperwallet_is_active_excluded_flag_active(self):
        Flag.objects.create(name='vendor:hyperwallet', everyone=True)
        Flag.objects.create(name='vendor:hyperwallet:excluded', everyone=True)

        is_active = check_hyperwallet_is_active(
            self.request, Decimal('100.00'), is_valid_royalty_advance=False
        )

        assert not is_active

    def test_check_hyperwallet_is_active_excluded_flag_inactive(self):
        Flag.objects.create(name='vendor:hyperwallet', everyone=True)
        Flag.objects.create(name='vendor:hyperwallet:excluded', everyone=False)

        is_active = check_hyperwallet_is_active(
            self.request, Decimal('100.00'), is_valid_royalty_advance=False
        )

        assert is_active

    def test_check_hyperwallet_is_active_inactive_user(self):
        Flag.objects.create(name='vendor:hyperwallet', everyone=True)
        self.request.user.is_active = False
        self.request.user.save()

        is_active = check_hyperwallet_is_active(
            self.request, Decimal('100.00'), is_valid_royalty_advance=False
        )

        assert not is_active

    def test_check_hyperwallet_is_active_flagged_user_balance(self):
        self.request.user.category = User.CATEGORY_FLAGGED
        self.request.user.save()

        is_active = check_hyperwallet_is_active(
            self.request, Decimal('100.00'), is_valid_royalty_advance=False
        )

        assert is_active

    def test_check_hyperwallet_is_active_flagged_user_advance(self):
        self.request.user.category = User.CATEGORY_FLAGGED
        self.request.user.save()

        is_active = check_hyperwallet_is_active(
            self.request, Decimal('100.00'), is_valid_royalty_advance=True
        )

        assert not is_active

    @mock.patch("amuse.vendor.hyperwallet.helpers.check_account_exists")
    def test_validate_email_checks_account(self, mock_check_account_exists):
        mock_check_account_exists.return_value = False
        payee_email = self.user.email

        hyperwallet_validate_email(self.user, payee_email)

        mock_check_account_exists.assert_called_once_with(payee_email)

    @mock.patch("amuse.vendor.hyperwallet.helpers.check_account_exists")
    def test_validate_email_raises_validation_error_for_existing_email(
        self, mock_check_account_exists
    ):
        payee_email = 'payee.email@amuse.io'
        mock_check_account_exists.return_value = True

        with pytest.raises(ValidationError):
            hyperwallet_validate_email(self.user, payee_email)

    @mock.patch("amuse.vendor.hyperwallet.helpers.check_account_exists")
    def test_validate_email_raises_validation_errors_for_validate_hyperwallet_account_email(
        self, mock_check_account_exists
    ):
        payee_email = 'payee.email@amuse.io'
        mock_check_account_exists.side_effect = HyperwalletAPIError()

        with pytest.raises(ValidationError):
            hyperwallet_validate_email(self.user, payee_email)

    @responses.activate
    def test_check_account_exists_detects_existing_user(self):
        email = 'existing.user@amuse.io'
        responses.add(
            responses.GET,
            '%s/%s?email=%s' % (settings.HYPERWALLET_ENDPOINT, 'users', email),
            status=200,
        )
        assert check_account_exists(email) is True

    @responses.activate
    def test_check_account_exists_detects_non_existing_user(self):
        email = 'non.existing.user@amuse.io'
        responses.add(
            responses.GET,
            '%s/%s?email=%s' % (settings.HYPERWALLET_ENDPOINT, 'users', email),
            status=204,
        )
        assert check_account_exists(email) is False

    @responses.activate
    def test_check_account_exists_raises_exception_for_unknown_response_code(self):
        email = 'i.am.a.teapot@amuse.io'
        responses.add(
            responses.GET,
            '%s/%s?email=%s' % (settings.HYPERWALLET_ENDPOINT, 'users', email),
            status=418,
        )
        with pytest.raises(HyperwalletAPIError):
            check_account_exists(email)

    @mock.patch("amuse.vendor.hyperwallet.client.get")
    def test_check_account_exists_raises_exception_for_api_error(self, mock_get):
        email = 'hyperwallet.api.error@amuse.io'
        mock_get.side_effect = HyperwalletAPIError
        with pytest.raises(HyperwalletAPIError):
            check_account_exists(email)

    @mock.patch("amuse.vendor.hyperwallet.client.get")
    def test_get_payments_returns_results(self, mock_get):
        mock_get.return_value = mock.Mock(status_code=200)
        assert get_payments("2020-01-01", "2020-01-31", 10, 0)

    @mock.patch("amuse.vendor.hyperwallet.client.get")
    def test_get_payments_returns_none(self, mock_get):
        mock_get.return_value = mock.Mock(status_code=204)
        assert get_payments("2020-01-01", "2020-01-31", 10, 0) is None

    @mock.patch("amuse.vendor.hyperwallet.client.get")
    def test_get_payments_raises_error(self, mock_get):
        mock_get.side_effect = HyperwalletAPIError
        with pytest.raises(HyperwalletAPIError):
            get_payments("2020-01-01", "2020-01-31", 10, 0)

    @mock.patch("amuse.vendor.hyperwallet.client.logger.info")
    @mock.patch("amuse.vendor.hyperwallet.client.update_withdrawal", return_value="xxx")
    def test_post_process_standard_withdrawal_success(
        self, mock_update_withdrawal, mock_logger
    ):
        payload = {
            "transaction_id": "xxx",
            "user_id": 11,
            "description": {"hyperwallet_payment_token": "hwhw"},
        }

        post_process_standard_withdrawal(payload)

        mock_update_withdrawal.assert_called_once_with(
            payload["transaction_id"], "is_complete", description=payload["description"]
        )
        mock_logger.assert_called_once()

    @mock.patch("amuse.vendor.hyperwallet.client.logger.error")
    @mock.patch("amuse.vendor.hyperwallet.client.update_withdrawal", return_value=None)
    def test_post_process_standard_withdrawal_fail(
        self, mock_update_withdrawal, mock_logger
    ):
        payload = {
            "transaction_id": "xxx",
            "user_id": 11,
            "description": {"hyperwallet_payment_token": "hwhw"},
        }

        post_process_standard_withdrawal(payload)

        mock_update_withdrawal.assert_called_once_with(
            payload["transaction_id"], "is_complete", description=payload["description"]
        )
        mock_logger.assert_called_once()

    @mock.patch("amuse.vendor.hyperwallet.client.logger.info")
    @mock.patch("amuse.vendor.hyperwallet.client.update_withdrawal", return_value="xxx")
    def test_cancel_standard_withdrawal_success(
        self, mock_update_withdrawal, mock_logger
    ):
        payload = {
            "transaction_id": "xxx",
            "user_id": 11,
            "description": {"hyperwallet_payment_token": "hwhw"},
        }

        cancel_standard_withdrawal(payload)

        mock_update_withdrawal.assert_called_once_with(
            payload["transaction_id"], "is_cancelled"
        )
        mock_logger.assert_called_once()

    @mock.patch("amuse.vendor.hyperwallet.client.logger.error")
    @mock.patch("amuse.vendor.hyperwallet.client.update_withdrawal", return_value=None)
    def test_cancel_standard_withdrawal_fail(self, mock_update_withdrawal, mock_logger):
        payload = {
            "transaction_id": "xxx",
            "user_id": 11,
            "description": {"hyperwallet_payment_token": "hwhw"},
        }

        cancel_standard_withdrawal(payload)

        mock_update_withdrawal.assert_called_once_with(
            payload["transaction_id"], "is_cancelled"
        )
        mock_logger.assert_called_once()

    @mock.patch("amuse.vendor.hyperwallet.client.update_royalty_advance_offer")
    def test_post_process_royalty_advance_success(self, mock_update):
        payload = {
            "transaction_id": "xxx",
            "user_id": self.user.id,
            "royalty_advance_id": "xxx",
            "action": "activate",
            "description": "blabla",
        }
        post_process_royalty_advance(payload)

    @mock.patch("amuse.vendor.hyperwallet.client.update_royalty_advance_offer")
    def test_post_process_royalty_advance_error(self, mock_update):
        mock_update.return_value = None
        payload = {
            "transaction_id": "xxx",
            "user_id": self.user.id,
            "royalty_advance_id": "xxx",
            "action": "activate",
            "description": "blabla",
        }

        with self.assertRaises(RoyaltyAdvanceActivateError):
            post_process_royalty_advance(payload)

    @mock.patch("amuse.vendor.hyperwallet.client.logger.info")
    @mock.patch("amuse.vendor.hyperwallet.client.update_royalty_advance_offer")
    def test_cancel_royalty_advance_success(self, mock_update, mock_logger):
        split_1 = RoyaltySplitFactory(
            user=self.user, status=RoyaltySplit.STATUS_ACTIVE, is_locked=True
        )
        split_2 = RoyaltySplitFactory(
            user=self.user, status=RoyaltySplit.STATUS_ACTIVE, is_locked=True
        )
        payload = {
            "transaction_id": "xxx",
            "user_id": self.user.id,
            "royalty_advance_id": "xxx",
            "split_ids_to_lock": [split_1.pk, split_2.pk],
            "action": "cancel",
            "description": "blabla",
        }
        cancel_royalty_advance(payload)

        mock_update.assert_called()
        mock_logger.assert_called()

        split_1.refresh_from_db()
        split_2.refresh_from_db()

        assert split_1.is_locked is False
        assert split_2.is_locked is False

    @mock.patch("amuse.vendor.hyperwallet.client.logger.warning")
    @mock.patch("amuse.vendor.hyperwallet.client.update_royalty_advance_offer")
    def test_cancel_royalty_advance_mismatching_splits_failure(
        self, mock_update, mock_logger
    ):
        split_1 = RoyaltySplitFactory(
            user=self.user, status=RoyaltySplit.STATUS_ACTIVE, is_locked=True
        )
        split_2 = RoyaltySplitFactory(
            user=self.user, status=RoyaltySplit.STATUS_ACTIVE, is_locked=False
        )
        payload = {
            "transaction_id": "xxx",
            "user_id": self.user.id,
            "royalty_advance_id": "xxx",
            "split_ids_to_lock": [split_1.pk, split_2.pk],
            "action": "cancel",
            "description": "blabla",
        }
        cancel_royalty_advance(payload)

        mock_update.assert_called()
        mock_logger.assert_called()

        split_1.refresh_from_db()
        split_2.refresh_from_db()

        assert split_1.is_locked is True
        assert split_2.is_locked is False

    @mock.patch("amuse.vendor.hyperwallet.client.logger.info")
    @mock.patch("amuse.vendor.hyperwallet.client.update_royalty_advance_offer")
    def test_cancel_royalty_advance_with_no_splits_success(
        self, mock_update, mock_logger
    ):
        payload = {
            "transaction_id": "xxx",
            "user_id": self.user.id,
            "royalty_advance_id": "xxx",
            "split_ids_to_lock": None,
            "action": "cancel",
            "description": "blabla",
        }
        cancel_royalty_advance(payload)

        mock_update.assert_called()

    @mock.patch("amuse.vendor.hyperwallet.client.logger.info")
    @mock.patch("amuse.vendor.hyperwallet.client.logger.warning")
    @mock.patch("amuse.vendor.hyperwallet.client.update_royalty_advance_offer")
    def test_cancel_royalty_advance_error(
        self, mock_update, mock_logger_warning, mock_logger_info
    ):
        mock_update.return_value = None
        payload = {
            "transaction_id": "xxx",
            "user_id": self.user.id,
            "royalty_advance_id": "xxx",
            "action": "cancel",
            "description": "blabla",
        }

        with self.assertRaises(RoyaltyAdvanceCancelError):
            cancel_royalty_advance(payload)

        mock_update.assert_called()
        mock_logger_info.assert_not_called()
        mock_logger_warning.assert_not_called()
