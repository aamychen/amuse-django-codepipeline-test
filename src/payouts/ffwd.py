import logging
import re
from decimal import Decimal

from rest_framework import serializers
from waffle import switch_is_active

from amuse.utils import log_func
from amuse.vendor.hyperwallet.client import cancel_royalty_advance
from slayer.clientwrapper import (
    validate_royalty_advance_offer,
    update_royalty_advance_offer,
)
from releases.models import RoyaltySplit, Release

logger = logging.getLogger(__name__)


class FFWDHelpers:
    @classmethod
    def _lock_splits(cls, split_ids_to_lock, user_id, offer_id, advance_id):
        split_ids_to_lock = [int(i) for i in split_ids_to_lock]

        logger.info(
            "Royalty advance offer %s user_id %s start split locking process for split_ids %s",
            offer_id,
            user_id,
            split_ids_to_lock,
        )

        split_ids_to_update = list(
            RoyaltySplit.objects.filter(
                id__in=split_ids_to_lock,
                user_id=user_id,
                status=RoyaltySplit.STATUS_ACTIVE,
                is_locked=False,
                # song__release__status=Release.STATUS_RELEASED,
            ).values_list("id", flat=True)
        )

        if sorted(split_ids_to_update) == sorted(split_ids_to_lock):
            RoyaltySplit.objects.filter(id__in=split_ids_to_update).update(
                is_locked=True
            )
            logger.info(
                "Royalty advance %s user_id %s validation is successful and locked splits %s",
                advance_id,
                user_id,
                split_ids_to_lock,
            )
        else:
            payload = {
                "user_id": user_id,
                "royalty_advance_id": advance_id,
                "split_ids_to_lock": split_ids_to_lock,
                "description": {},
            }
            cancel_royalty_advance(payload, unlock_splits=False)
            logger.error(
                "Royalty advance %s user_id %s lock splits %s failed as it doesn't match %s splits returned from the database.",
                advance_id,
                user_id,
                split_ids_to_lock,
                split_ids_to_update,
            )
            raise serializers.ValidationError(
                {
                    "royalty_advance_offer_id": [
                        "System error occured when accepting offer. Please try again."
                    ]
                }
            )

    @classmethod
    def validate_royalty_advance_offer(cls, user_id, offer_id):
        """
        This value is only set when a user wants to accept an advance offer.
        """
        logger.info(
            f"Start validate_royalty_advance_offer - user ID: {user_id}, offer ID: {offer_id}"
        )
        validated_offer = validate_royalty_advance_offer(
            user_id,
            offer_id,
            create_pending_transactions=True,
        )
        logger.info(
            f"End validate_royalty_advance_offer - user ID: {user_id}, return value: {validated_offer}"
        )
        offer_amount = Decimal(validated_offer["withdrawal_total"])
        advance_id = validated_offer["royalty_advance_id"]

        if validated_offer and validated_offer.get("is_valid"):
            split_ids_to_lock = validated_offer["royalty_advance_offer"].get(
                "split_ids_for_locking"
            )
            if split_ids_to_lock:
                splits = RoyaltySplit.objects.filter(id__in=split_ids_to_lock)
                for split in splits:
                    release = split.song.release
                    if not release.status == Release.STATUS_RELEASED:
                        logger.warning(
                            "FFWD validation - Illegal status of release %s: %s. ",
                            release.id,
                            release.status,
                        )
                        cancellation_response = update_royalty_advance_offer(
                            user_id,
                            advance_id,
                            "cancel",
                            description="New Hyperwallet API integration API",
                        )
                        logger.info(
                            f'FFWD cancelled, response: {cancellation_response}'
                        )
                        raise serializers.ValidationError(
                            {
                                "royalty_advance_offer_id": [
                                    "Inconsistent release status. Please try again."
                                ]
                            }
                        )

                cls._lock_splits(split_ids_to_lock, user_id, offer_id, advance_id)

            else:
                logger.info(
                    "Royalty advance offer %s user_id %s has no splits to lock.",
                    offer_id,
                    user_id,
                )

        else:
            logger.info(
                "Validation of Royalty Advance offer %s for user_id %s failed with response %s.",
                offer_id,
                user_id,
                validated_offer,
            )
            raise serializers.ValidationError(
                {"royalty_advance_offer_id": ["Offer has expired. Please try again."]}
            )

        if offer_amount > 0.0 and advance_id:
            return {'advance_id': advance_id, 'raw_withdrawal_total': offer_amount}

        else:
            raise serializers.ValidationError(
                {"royalty_advance_offer_id": ["Offer not valid. Please try again."]}
            )

    @staticmethod
    def unlock_splits(user_id, splits_to_unlock=[]):
        if not splits_to_unlock:
            splits_to_update = list(
                RoyaltySplit.objects.filter(
                    user_id=user_id, is_owner=True, is_locked=True
                ).values_list("id", flat=True)
            )
            RoyaltySplit.objects.filter(id__in=splits_to_update).update(is_locked=False)
            logger.info(f"Royalty advance unlocked splits_ids={splits_to_update}")
        else:
            RoyaltySplit.objects.filter(id__in=splits_to_unlock).update(is_locked=False)
            logger.info(f"Royalty advance unlocked splits_ids={splits_to_unlock}")
