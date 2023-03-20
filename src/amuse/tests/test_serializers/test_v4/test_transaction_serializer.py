from collections import OrderedDict
from decimal import Decimal
from unittest import mock

import responses
from django.http import HttpRequest
from rest_framework.serializers import ValidationError
from rest_framework.test import APIRequestFactory

from amuse.api.v4.serializers.transaction import (
    EMAIL_MISMATCH_MESSAGE,
    POSTAL_CODE_REQUIRED_MESSAGE,
    NAME_TOO_LONG_MESSAGE,
    NAME_INVALID_CHARACTERS_MESSAGE,
)
from amuse.api.v4.serializers.transaction import (
    TransactionPayeeSerializerExistingHyperwalletUser as TransactionExistingPayeeSerializer,
)
from amuse.api.v4.serializers.transaction import (
    TransactionPayeeSerializerNewHyperwalletUser as TransactionPayeeSerializer,
)
from amuse.tests.test_api.base import AmuseAPITestCase
from amuse.vendor.revenue.client import URL_RECORD_HYPERWALLET_WITHDRAWAL, get_wallet
from users.models import UserMetadata
from users.tests.factories import UserFactory


class TestTransactionSerializer(AmuseAPITestCase):
    @responses.activate
    @mock.patch("amuse.tasks.zendesk_create_or_update_user")
    def setUp(self, mock_zendesk):
        self.user = UserFactory(country="SE")
        self.data = {"email": self.user.email}

        django_request = HttpRequest()
        factory = APIRequestFactory()
        self.request = factory.post('/users/withdrawal/', {})
        self.request._request = django_request
        self.request.user = self.user
        self.request._request.user = self.user
        self.request.type = "person"

    @responses.activate
    @mock.patch(
        "amuse.api.v4.serializers.transaction.TransactionPayeeSerializerV4Base._record_withdrawal"
    )
    @mock.patch("amuse.api.v4.serializers.transaction.get_balance", return_value=12.44)
    @mock.patch(
        "amuse.api.v4.serializers.transaction.hyperwallet_validate_email",
        return_value=False,
    )
    @mock.patch("amuse.api.v4.serializers.transaction.validate_phone")
    @mock.patch(
        "amuse.api.v4.serializers.transaction.check_hyperwallet_is_active",
        return_value=True,
    )
    def test_swedish_user_no_hyperwallet_account_is_valid(
        self,
        mock_check_hyperwallet,
        mock_validate_phone,
        mock_validate_email,
        mock_get_balance,
        mock_record_withdrawal,
    ):
        mock_record_withdrawal.return_value = "xxx"
        self.user.phone = "+46704554090"
        self.user.save()
        self.data["postal_code"] = "123456"

        mock_validate_phone.return_value = self.user.phone
        self.data["address"] = "Stockholm"

        serializer = TransactionPayeeSerializer(
            hyperwallet_user_token=None, data=self.data, request=self.request
        )

        assert serializer.is_valid()
        assert serializer.validated_data["postal_code"] is None
        assert serializer.transaction_id == "xxx"

    @responses.activate
    @mock.patch(
        "amuse.api.v4.serializers.transaction.TransactionPayeeSerializerV4Base._record_withdrawal"
    )
    @mock.patch("amuse.api.v4.serializers.transaction.get_balance", return_value=12.44)
    @mock.patch(
        "amuse.api.v4.serializers.transaction.check_hyperwallet_is_active",
        return_value=True,
    )
    def test_swedish_user_existing_hyperwallet_account_is_valid(
        self, mock_check_hyperwallet, mock_get_balance, mock_record_withdrawal
    ):
        usermetadata = UserMetadata.objects.create(
            user=self.user, hyperwallet_user_token="ttt"
        )
        mock_record_withdrawal.return_value = "xxx"

        serializer = TransactionExistingPayeeSerializer(
            hyperwallet_user_token=usermetadata.hyperwallet_user_token,
            data={},
            request=self.request,
        )

        assert serializer.is_valid()
        assert serializer.transaction_id == "xxx"

    @responses.activate
    @mock.patch(
        "amuse.api.v4.serializers.transaction.TransactionPayeeSerializerV4Base._record_withdrawal"
    )
    @mock.patch("amuse.api.v4.serializers.transaction.get_balance", return_value=12.44)
    @mock.patch(
        "amuse.api.v4.serializers.transaction.hyperwallet_validate_email",
        return_value=False,
    )
    @mock.patch("amuse.api.v4.serializers.transaction.validate_phone")
    @mock.patch(
        "amuse.api.v4.serializers.transaction.check_hyperwallet_is_active",
        return_value=True,
    )
    def test_russian_user_extract_valid_postal_code(
        self,
        mock_check_hyperwallet,
        mock_validate_phone,
        mock_validate_email,
        mock_get_balance,
        mock_record_withdrawal,
    ):
        self.user.phone = "+79963801821"
        self.user.country = "RU"
        self.user.save()
        self.data["postal_code"] = "630091"

        serializer = TransactionPayeeSerializer(
            hyperwallet_user_token=None, data=self.data, request=self.request
        )

        assert serializer.is_valid()
        assert serializer.validated_data["postal_code"] == "630091"

    @responses.activate
    @mock.patch("amuse.api.v4.serializers.transaction.get_balance", return_value=12.44)
    @mock.patch(
        "amuse.api.v4.serializers.transaction.hyperwallet_validate_email",
        return_value=False,
    )
    @mock.patch("amuse.api.v4.serializers.transaction.validate_phone")
    @mock.patch(
        "amuse.api.v4.serializers.transaction.check_hyperwallet_is_active",
        return_value=True,
    )
    def test_russian_user_extract_invalid_postal_code(
        self,
        mock_check_hyperwallet,
        mock_validate_phone,
        mock_validate_email,
        mock_get_balance,
    ):
        self.user.phone = "+79963801821"
        self.user.country = "RU"
        self.user.save()
        self.data["postal_code"] = "1960"

        serializer = TransactionPayeeSerializer(
            hyperwallet_user_token=None, data=self.data, request=self.request
        )

        assert not serializer.is_valid()
        assert str(serializer.errors["postal_code"][0]) == POSTAL_CODE_REQUIRED_MESSAGE

    @responses.activate
    @mock.patch(
        "amuse.api.v4.serializers.transaction.TransactionPayeeSerializerV4Base._record_withdrawal"
    )
    @mock.patch("amuse.api.v4.serializers.transaction.get_balance", return_value=12.44)
    @mock.patch(
        "amuse.api.v4.serializers.transaction.hyperwallet_validate_email",
        return_value=False,
    )
    @mock.patch("amuse.api.v4.serializers.transaction.validate_phone")
    @mock.patch(
        "amuse.api.v4.serializers.transaction.check_hyperwallet_is_active",
        return_value=True,
    )
    def test_ukrainian_user_extract_valid_postal_code(
        self,
        mock_check_hyperwallet,
        mock_validate_phone,
        mock_validate_email,
        mock_get_balance,
        mock_record_withdrawal,
    ):
        self.user.phone = "+380667828152"
        self.user.country = "UA"
        self.user.save()
        self.data["postal_code"] = "77311"

        serializer = TransactionPayeeSerializer(
            hyperwallet_user_token=None, data=self.data, request=self.request
        )

        assert serializer.is_valid()
        assert serializer.validated_data["postal_code"] == "77311"

    @responses.activate
    @mock.patch("amuse.api.v4.serializers.transaction.get_balance", return_value=12.44)
    @mock.patch(
        "amuse.api.v4.serializers.transaction.hyperwallet_validate_email",
        return_value=False,
    )
    @mock.patch("amuse.api.v4.serializers.transaction.validate_phone")
    @mock.patch(
        "amuse.api.v4.serializers.transaction.check_hyperwallet_is_active",
        return_value=True,
    )
    def test_ukrainian_user_extract_invalid_postal_code(
        self,
        mock_check_hyperwallet,
        mock_validate_phone,
        mock_validate_email,
        mock_get_balance,
    ):
        self.user.phone = "+380667828152"
        self.user.country = "UA"
        self.user.save()
        self.data["postal_code"] = "08149994"

        serializer = TransactionPayeeSerializer(
            hyperwallet_user_token=None, data=self.data, request=self.request
        )

        assert not serializer.is_valid()
        assert str(serializer.errors["postal_code"][0]) == POSTAL_CODE_REQUIRED_MESSAGE

    @responses.activate
    @mock.patch("amuse.api.v4.serializers.transaction.get_balance", return_value=12.44)
    @mock.patch(
        "amuse.api.v4.serializers.transaction.hyperwallet_validate_email",
        return_value=False,
    )
    @mock.patch("amuse.api.v4.serializers.transaction.validate_phone")
    @mock.patch(
        "amuse.api.v4.serializers.transaction.check_hyperwallet_is_active",
        return_value=True,
    )
    def test_mismatching_emails_raises_error(
        self,
        mock_check_hyperwallet,
        mock_validate_phone,
        mock_validate_email,
        mock_get_balance,
    ):
        self.data["email"] = "test_payee@amuse.io"

        serializer = TransactionPayeeSerializer(
            hyperwallet_user_token=None, data=self.data, request=self.request
        )

        assert not serializer.is_valid()
        assert str(serializer.errors["email"][0]) == EMAIL_MISMATCH_MESSAGE

    @responses.activate
    @mock.patch(
        "amuse.api.v4.serializers.transaction.TransactionPayeeSerializerV4Base._record_withdrawal"
    )
    @mock.patch("amuse.api.v4.serializers.transaction.get_balance", return_value=12.44)
    @mock.patch(
        "amuse.api.v4.serializers.transaction.hyperwallet_validate_email",
        return_value=False,
    )
    @mock.patch("amuse.api.v4.serializers.transaction.validate_phone")
    @mock.patch(
        "amuse.api.v4.serializers.transaction.check_hyperwallet_is_active",
        return_value=True,
    )
    def test_returns_get_wallet_function(
        self,
        mock_check_hyperwallet,
        mock_validate_phone,
        mock_validate_email,
        mock_get_balance,
        mock_record_withdrawal,
    ):
        self.user.phone = "+46704554090"
        self.user.save()
        self.data["postal_code"] = "123456"

        mock_validate_phone.return_value = self.user.phone
        self.data["address"] = "Stockholm"

        serializer = TransactionPayeeSerializer(
            hyperwallet_user_token=None, data=self.data, request=self.request
        )

        assert serializer.is_valid()
        assert serializer.get_transactions_func == get_wallet

    @responses.activate
    @mock.patch("amuse.api.v4.serializers.transaction.get_balance", return_value=12.44)
    @mock.patch(
        "amuse.api.v4.serializers.transaction.hyperwallet_validate_email",
        return_value=False,
    )
    @mock.patch("amuse.api.v4.serializers.transaction.validate_phone")
    @mock.patch(
        "amuse.api.v4.serializers.transaction.check_hyperwallet_is_active",
        return_value=True,
    )
    def test_returns_error_on_failed_record_withdrawal(
        self,
        mock_check_hyperwallet,
        mock_validate_phone,
        mock_validate_email,
        mock_get_balance,
    ):
        responses.add(responses.POST, URL_RECORD_HYPERWALLET_WITHDRAWAL, status=500)
        self.user.phone = "+46704554090"
        self.user.save()
        self.data["postal_code"] = "123456"

        mock_validate_phone.return_value = self.user.phone
        self.data["address"] = "Stockholm"

        serializer = TransactionPayeeSerializer(
            hyperwallet_user_token=None, data=self.data, request=self.request
        )

        assert not serializer.is_valid()
        assert (
            str(serializer.errors["non_field_errors"][0])
            == "System error. Please try again."
        )

    @responses.activate
    @mock.patch(
        "amuse.api.v4.serializers.transaction.TransactionPayeeSerializerV4Base._record_withdrawal"
    )
    @mock.patch("amuse.api.v4.serializers.transaction.get_balance", return_value=12.00)
    @mock.patch(
        "amuse.api.v4.serializers.transaction.hyperwallet_validate_email",
        return_value=False,
    )
    @mock.patch("amuse.api.v4.serializers.transaction.validate_phone")
    @mock.patch(
        "amuse.api.v4.serializers.transaction.check_hyperwallet_is_active",
        return_value=True,
    )
    @mock.patch(
        "amuse.api.v4.serializers.transaction.switch_is_active", return_value=False
    )
    def test_record_withdrawal_is_called_once_all_validations_are_finished(
        self,
        mock_switch,
        mock_check_hyperwallet,
        mock_validate_phone,
        mock_validate_email,
        mock_get_balance,
        mock_record_withdrawal,
    ):
        self.user.phone = "+46704554090"
        self.user.save()
        self.data["postal_code"] = "123456"
        self.data["address"] = "Stockholm"

        mock_validate_phone.return_value = self.user.phone
        mock_record_withdrawal.return_value = "xxx"

        mock_manager = mock.Mock()
        mock_manager.attach_mock(mock_switch, "mock_switch")
        mock_manager.attach_mock(mock_get_balance, "mock_balance")
        mock_manager.attach_mock(mock_check_hyperwallet, "mock_check_hyperwallet")
        mock_manager.attach_mock(mock_validate_phone, "mock_validate_phone")
        mock_manager.attach_mock(mock_validate_email, "mock_validate_email")
        mock_manager.attach_mock(mock_record_withdrawal, "mock_record_withdrawal")

        serializer = TransactionPayeeSerializer(
            hyperwallet_user_token=None, data=self.data, request=self.request
        )

        assert serializer.is_valid()

        mock_manager.assert_has_calls(
            [
                mock.call.mock_switch("withdrawals:disabled"),
                mock.call.mock_balance(self.user.pk),
                mock.call.mock_check_hyperwallet(self.request, Decimal("12"), False),
                mock.call.mock_validate_phone(self.user),
                mock.call.mock_validate_email(self.user, self.data["email"]),
                mock.call.mock_record_withdrawal(
                    OrderedDict(
                        {
                            "email": self.data["email"],
                            "postal_code": None,  # We only return postal_code for RU/UA users
                        }
                    )
                ),
            ]
        )

    @responses.activate
    @mock.patch(
        "amuse.api.v4.serializers.transaction.TransactionPayeeSerializerV4Base._record_withdrawal"
    )
    @mock.patch("amuse.api.v4.serializers.transaction.get_balance", return_value=12.44)
    @mock.patch(
        "amuse.api.v4.serializers.transaction.hyperwallet_validate_email",
        return_value=False,
    )
    @mock.patch("amuse.api.v4.serializers.transaction.validate_phone")
    @mock.patch(
        "amuse.api.v4.serializers.transaction.check_hyperwallet_is_active",
        return_value=True,
    )
    def test_validate_valid_name(
        self,
        mock_check_hyperwallet,
        mock_validate_phone,
        mock_validate_email,
        mock_get_balance,
        mock_record_withdrawal,
    ):
        mock_record_withdrawal.return_value = "xxx"
        self.user.first_name = "O'Donald"
        self.user.last_name = "Trump, Junior-the-third"
        self.user.save()

        serializer = TransactionPayeeSerializer(
            hyperwallet_user_token=None, data=self.data, request=self.request
        )

        assert serializer.is_valid()
        assert serializer.transaction_id == "xxx"

    @responses.activate
    @mock.patch(
        "amuse.api.v4.serializers.transaction.TransactionPayeeSerializerV4Base._record_withdrawal"
    )
    @mock.patch("amuse.api.v4.serializers.transaction.get_balance", return_value=12.44)
    @mock.patch(
        "amuse.api.v4.serializers.transaction.hyperwallet_validate_email",
        return_value=False,
    )
    @mock.patch("amuse.api.v4.serializers.transaction.validate_phone")
    @mock.patch(
        "amuse.api.v4.serializers.transaction.check_hyperwallet_is_active",
        return_value=True,
    )
    def test_validate_valid_japanese_name(
        self,
        mock_check_hyperwallet,
        mock_validate_phone,
        mock_validate_email,
        mock_get_balance,
        mock_record_withdrawal,
    ):
        mock_record_withdrawal.return_value = "xxx"
        self.user.first_name = "天照"
        self.user.last_name = "大御神"
        self.user.save()

        serializer = TransactionPayeeSerializer(
            hyperwallet_user_token=None, data=self.data, request=self.request
        )

        assert serializer.is_valid()
        assert serializer.transaction_id == "xxx"

    @responses.activate
    @mock.patch(
        "amuse.api.v4.serializers.transaction.TransactionPayeeSerializerV4Base._record_withdrawal"
    )
    @mock.patch("amuse.api.v4.serializers.transaction.get_balance", return_value=12.44)
    @mock.patch(
        "amuse.api.v4.serializers.transaction.hyperwallet_validate_email",
        return_value=False,
    )
    @mock.patch("amuse.api.v4.serializers.transaction.validate_phone")
    @mock.patch(
        "amuse.api.v4.serializers.transaction.check_hyperwallet_is_active",
        return_value=True,
    )
    def test_validate_valid_name_with_unicode_characters(
        self,
        mock_check_hyperwallet,
        mock_validate_phone,
        mock_validate_email,
        mock_get_balance,
        mock_record_withdrawal,
    ):
        mock_record_withdrawal.return_value = "xxx"
        self.user.first_name = "Ö'Döñáld"
        self.user.last_name = "Trümp, Jünior-the-third"
        self.user.save()

        serializer = TransactionPayeeSerializer(
            hyperwallet_user_token=None, data=self.data, request=self.request
        )

        assert serializer.is_valid()
        assert serializer.transaction_id == "xxx"

    @mock.patch("amuse.api.v4.serializers.transaction.get_balance", return_value=12.44)
    @mock.patch(
        "amuse.api.v4.serializers.transaction.check_hyperwallet_is_active",
        return_value=True,
    )
    def test_validate_invalid_name_with_too_long_name(
        self, mock_check_hyperwallet, mock_get_balance
    ):
        self.user.first_name = "O'Donaldxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
        self.user.last_name = "Trump, Junior-the-third"
        self.user.save()

        serializer = TransactionPayeeSerializer(
            hyperwallet_user_token=None, data=self.data, request=self.request
        )

        assert not serializer.is_valid()
        assert (
            str(serializer.errors["non_field_errors"][0])
            == NAME_TOO_LONG_MESSAGE % "first"
        )

    @mock.patch("amuse.api.v4.serializers.transaction.get_balance", return_value=12.44)
    @mock.patch(
        "amuse.api.v4.serializers.transaction.check_hyperwallet_is_active",
        return_value=True,
    )
    def test_validate_invalid_name_with_invalid_symbol_in_name(
        self, mock_check_hyperwallet, mock_get_balance
    ):
        self.user.first_name = "O'Donald$$"
        self.user.last_name = "Trump, Junior-the-third"
        self.user.save()

        serializer = TransactionPayeeSerializer(
            hyperwallet_user_token=None, data=self.data, request=self.request
        )

        assert not serializer.is_valid()
        assert (
            str(serializer.errors["non_field_errors"][0])
            == NAME_INVALID_CHARACTERS_MESSAGE % "first"
        )

    @mock.patch("amuse.api.v4.serializers.transaction.get_balance", return_value=12.44)
    @mock.patch(
        "amuse.api.v4.serializers.transaction.check_hyperwallet_is_active",
        return_value=True,
    )
    def test_validate_invalid_name_with_digit_in_name(
        self, mock_check_hyperwallet, mock_get_balance
    ):
        self.user.first_name = "O'Donald"
        self.user.last_name = "Trump, Junior-the-3"
        self.user.save()

        serializer = TransactionPayeeSerializer(
            hyperwallet_user_token=None, data=self.data, request=self.request
        )

        assert not serializer.is_valid()
        assert (
            str(serializer.errors["non_field_errors"][0])
            == NAME_INVALID_CHARACTERS_MESSAGE % "last"
        )
