import logging
import re
from decimal import Decimal

from rest_framework import serializers
from waffle import switch_is_active

from amuse.vendor.hyperwallet.client import cancel_royalty_advance
from amuse.vendor.hyperwallet.helpers import (
    check_hyperwallet_is_active,
    hyperwallet_validate_email,
    validate_phone,
)
from amuse.vendor.revenue.client import get_balance, get_wallet, record_withdrawal
from slayer.clientwrapper import validate_royalty_advance_offer
from releases.models import RoyaltySplit


logger = logging.getLogger(__name__)
MAINTENANCE_MESSAGE = "You cannot make withdrawals at the moment due to maintenance. Please try again later. Thank you for your patience!"
POSTAL_CODE_REQUIRED_MESSAGE = "Please enter a valid postal code."
VERIFY_EMAIL_MESSAGE = "Please verify your email address in order to make withdrawals."
EMAIL_MISMATCH_MESSAGE = "Your Hyperwallet email must be the same as your Amuse account email. How to add additional email addresses to Paypal: https://join.amu.se/fh1"
NAME_TOO_LONG_MESSAGE = "Your %s name must be shorter than 50 characters. Please go to Account -> User Profile and update your name."
NAME_INVALID_CHARACTERS_MESSAGE = "Your %s name includes invalid characters. Please go to Account -> User Profile and update your name."


class TransactionPayeeSerializerV4Base(serializers.Serializer):
    royalty_advance_offer_id = serializers.UUIDField(
        required=False, format='hex_verbose'
    )

    def __init__(self, request, hyperwallet_user_token, *args, **kwargs):
        super().__init__(request, *args, **kwargs)

        self.request = request
        self.withdrawal_amount = Decimal("0.00")
        self.hyperwallet_is_active = False
        self.hyperwallet_user_token = hyperwallet_user_token
        self.validated_phone = None
        self.is_valid_royalty_advance = False
        self.transaction_id = None
        self.royalty_advance_id = None
        self.royalty_advance_offer_id = None
        self.is_valid_royalty_advance = False
        self.validated_offer = None
        self.split_ids_to_lock = None
        self.get_transactions_func = get_wallet

    def to_internal_value(self, data):
        ret = super().to_internal_value(data)

        if ret.get("royalty_advance_offer_id"):
            ret['royalty_advance_offer_id'] = str(ret["royalty_advance_offer_id"])
        return ret

    def validate(self, data):
        if switch_is_active('withdrawals:disabled'):
            raise serializers.ValidationError(MAINTENANCE_MESSAGE)

        self.royalty_advance_offer_id = data.get("royalty_advance_offer_id")

        if self.royalty_advance_offer_id:
            self.royalty_advance_offer_id = str(self.royalty_advance_offer_id)
            self.withdrawal_amount = self._pre_validate_royalty_advance_offer()
        else:
            self.withdrawal_amount = self._get_balance()

        self.hyperwallet_is_active = check_hyperwallet_is_active(
            self.request, self.withdrawal_amount, self.is_valid_royalty_advance
        )

        if self.request.user.email_verified is False:
            raise serializers.ValidationError(VERIFY_EMAIL_MESSAGE)

        if not self.hyperwallet_is_active:
            logger.info('Blocked withdrawal for user_id %s' % self.request.user.id)
            raise serializers.ValidationError(
                "You cannot make withdrawals at the moment. Please contact support."
            )

        return data

    def _pre_validate_royalty_advance_offer(self):
        """
        Pre validate the offer so we can get the amount
        """
        pre_validated_offer = validate_royalty_advance_offer(
            self.request.user.pk,
            self.royalty_advance_offer_id,
            create_pending_transactions=False,
        )

        if not pre_validated_offer or not pre_validated_offer.get("is_valid"):
            logger.info(
                "Pre Validation of Royalty Advance offer %s for user_id %s failed with response %s.",
                self.royalty_advance_offer_id,
                self.request.user.pk,
                pre_validated_offer,
            )
            raise serializers.ValidationError(
                {"royalty_advance_offer_id": ["Offer is not valid. Please try again."]}
            )

        self.is_valid_royalty_advance = True

        return Decimal(pre_validated_offer["withdrawal_total"])

    def _validate_royalty_advance_offer(self):
        """
        This value is only set when a user wants to accept an advance offer.
        """

        # Reset this as it can be True from pre-validation but we want to base the
        # rest of the flow on the real validation.
        self.is_valid_royalty_advance = False

        self.validated_offer = validate_royalty_advance_offer(
            self.request.user.pk,
            self.royalty_advance_offer_id,
            create_pending_transactions=True,
        )

        if self.validated_offer and self.validated_offer.get("is_valid"):
            self.split_ids_to_lock = self.validated_offer["royalty_advance_offer"].get(
                "split_ids_for_locking"
            )
            self.withdrawal_amount = Decimal(self.validated_offer["withdrawal_total"])
            self.royalty_advance_id = self.validated_offer.get("royalty_advance_id")

            if self.split_ids_to_lock:
                self._lock_splits()
            else:
                logger.info(
                    "Royalty advance offer %s user_id %s has no splits to lock.",
                    self.royalty_advance_offer_id,
                    self.request.user.pk,
                )

            self.is_valid_royalty_advance = True
        else:
            logger.info(
                "Validation of Royalty Advance offer %s for user_id %s failed with response %s.",
                self.royalty_advance_offer_id,
                self.request.user.pk,
                self.validated_offer,
            )
            raise serializers.ValidationError(
                {"royalty_advance_offer_id": ["Offer has expired. Please try again."]}
            )

        return self.validated_offer.get("royalty_advance_id")

    def _get_balance(self):
        """
        Return either only the balance or balance + advance based on if it's an
        accepted valid Royalty Advance offer.
        """
        if self.is_valid_royalty_advance:
            balance = self.validated_offer.get("withdrawal_total")
        else:
            balance = get_balance(self.request.user.id)

        if balance is None or balance <= 0:
            raise serializers.ValidationError("Zero balance")

        return Decimal(balance)

    def _record_withdrawal(self, data):
        revenue_payload = {
            "user_id": self.request.user.pk,
            "total": self.withdrawal_amount,
            "description": dict(data),
            "currency": "USD",
        }

        transaction_id = record_withdrawal(revenue_payload, is_pending=True)
        if transaction_id is None:
            raise serializers.ValidationError("System error. Please try again.")

        return transaction_id

    def _lock_splits(self):
        self.split_ids_to_lock = [int(i) for i in self.split_ids_to_lock]

        logger.info(
            "Royalty advance offer %s user_id %s start split locking process for split_ids %s",
            self.royalty_advance_offer_id,
            self.request.user.pk,
            self.split_ids_to_lock,
        )

        # Remove label splits (encoded as -1 in list)
        self.split_ids_to_lock = list(
            filter(lambda split_id: split_id > 0, self.split_ids_to_lock)
        )

        # Get all Split object included in advance
        splits_from_advance = set(
            list(
                RoyaltySplit.objects.filter(
                    id__in=self.split_ids_to_lock, user_id=self.request.user.pk
                )
            )
        )

        # Filter for owner splits
        splits_to_update = list(
            filter(lambda split: split.is_owner == True, splits_from_advance)
        )
        split_ids_to_update = set(list(map(lambda split: split.id, splits_to_update)))

        # make sure we found all splits in advance
        if split_ids_to_update.issubset(set(self.split_ids_to_lock)) and len(
            splits_from_advance
        ) == len(self.split_ids_to_lock):
            RoyaltySplit.objects.filter(id__in=list(split_ids_to_update)).update(
                is_locked=True
            )
            logger.info(
                "Royalty advance %s user_id %s validation is successful and locked splits %s",
                self.royalty_advance_id,
                self.request.user.pk,
                self.split_ids_to_lock,
            )
        else:
            payload = {
                "user_id": self.request.user.pk,
                "royalty_advance_id": self.royalty_advance_id,
                "split_ids_to_lock": self.split_ids_to_lock,
                "description": {},
            }
            cancel_royalty_advance(payload, unlock_splits=False)
            logger.error(
                "Royalty advance %s user_id %s lock splits %s failed as it doesn't match %s splits returned from the database.",
                self.royalty_advance_id,
                self.request.user.pk,
                self.split_ids_to_lock,
                split_ids_to_update,
            )
            raise serializers.ValidationError(
                {
                    "royalty_advance_offer_id": [
                        "System error occured when accepting offer. Please try again."
                    ]
                }
            )


class TransactionPayeeSerializerNewHyperwalletUser(TransactionPayeeSerializerV4Base):
    email = serializers.EmailField()
    postal_code = serializers.CharField(required=False, allow_blank=True)

    def validate(self, data):
        data = super().validate(data)

        self._validate_name()
        self.validated_phone = validate_phone(self.request.user)

        if data['email'] != self.request.user.email:
            raise serializers.ValidationError({'email': [EMAIL_MISMATCH_MESSAGE]})

        hyperwallet_validate_email(self.request.user, self.request.user.email)

        if self.royalty_advance_offer_id:
            self.transaction_id = self._validate_royalty_advance_offer()
        else:
            self.transaction_id = self._record_withdrawal(data)

        return data

    def validate_postal_code(self, value):
        user_country = self.request.user.country
        patterns = {"UA": r"\b(?!00)\d{5}\b", "RU": r"\b\d{6}\b"}

        if user_country in ("RU", "UA"):
            match = re.search(patterns[user_country], value)

            if not match:
                raise serializers.ValidationError(POSTAL_CODE_REQUIRED_MESSAGE)

            return value
        else:
            return None

    def _validate_name(self):
        """
        Max 50 characters. Allows letters space and ' , - .
        Hyperwallet only allows the special symbols in conjuction with letters but we
        will ignore that for now as this regex will filter out the majority of the
        invalid names.
        """
        pattern = re.compile(r"(?![^\W\d]|[ \.\'\_\-\,]).")

        first_name = self.request.user.first_name
        last_name = self.request.user.last_name

        if len(first_name) > 50:
            raise serializers.ValidationError(
                {"non_field_errors": NAME_TOO_LONG_MESSAGE % "first"}
            )

        if len(last_name) > 50:
            raise serializers.ValidationError(
                {"non_field_errors": NAME_TOO_LONG_MESSAGE % "last"}
            )

        if pattern.findall(first_name):
            raise serializers.ValidationError(
                {"non_field_errors": NAME_INVALID_CHARACTERS_MESSAGE % "first"}
            )

        if pattern.findall(last_name):
            raise serializers.ValidationError(
                {"non_field_errors": NAME_INVALID_CHARACTERS_MESSAGE % "last"}
            )


class TransactionPayeeSerializerExistingHyperwalletUser(
    TransactionPayeeSerializerV4Base
):
    def validate(self, data):
        data = super().validate(data)

        if self.royalty_advance_offer_id:
            self.transaction_id = self._validate_royalty_advance_offer()
        else:
            self.transaction_id = self._record_withdrawal(data)

        return data
