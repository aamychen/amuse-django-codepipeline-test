from unittest import mock
from unittest.mock import patch

import pytest

from amuse import serializers
from amuse.tests.helpers import mock_validate_offer
from releases import models
from decimal import Decimal
from django.test import TestCase
from users.tests.factories import UserFactory
from releases.tests.factories import RoyaltySplitFactory, SongFactory, ReleaseFactory
from payouts.ffwd import FFWDHelpers
from releases.models import RoyaltySplit
from pyslayer.services.revenue import (
    ValidateAppRoyaltyAdvanceOfferResponse,
)


class TestFFWDHelper(TestCase):
    @mock.patch("amuse.tasks.zendesk_create_or_update_user")
    def setUp(self, mocked_task):
        self.user = UserFactory(country="US", email='test@example.com')
        self.released_release = ReleaseFactory(
            status=models.Release.STATUS_RELEASED, user=self.user
        )
        self.takedown_release = ReleaseFactory(
            status=models.Release.STATUS_TAKEDOWN, user=self.user
        )
        self.song = SongFactory(
            meta_language=None, meta_audio_locale=None, release=self.released_release
        )
        self.song2 = SongFactory(
            meta_language=None, meta_audio_locale=None, release=self.takedown_release
        )
        self.split1 = RoyaltySplitFactory(
            song=self.song,
            user=self.user,
            rate=Decimal("1.0"),
            revision=1,
            status=RoyaltySplit.STATUS_ACTIVE,
            is_owner=True,
            is_locked=False,
        )
        self.split2 = RoyaltySplitFactory(
            song=self.song2,
            user=self.user,
            rate=Decimal("1.0"),
            revision=1,
            status=RoyaltySplit.STATUS_ACTIVE,
            is_owner=False,
            is_locked=False,
        )
        self.validated_offer = {
            'is_valid': True,
            'withdrawal_total': 300.0,
            'royalty_advance_offer_id': 'cxjsdni1',
            'royalty_advance_offer': {
                'split_ids_for_locking': [self.split1.pk, self.split2.pk]
            },
        }
        self.mocked_offer = mock_validate_offer(
            user_id=self.user.pk,
            royalty_advance_offer_id=self.validated_offer['royalty_advance_offer_id'],
            split_ids=[self.split1.pk, self.split2.pk],
            withdrawal_total=self.validated_offer['withdrawal_total'],
            royalty_advance_id="12345678-1234-1234-1234-123456789012",
        )
        self.mocked_offer_no_splits = mock_validate_offer(
            user_id=self.user.pk,
            royalty_advance_offer_id=self.validated_offer['royalty_advance_offer_id'],
            split_ids=None,
            withdrawal_total=self.validated_offer['withdrawal_total'],
            royalty_advance_id="12345678-1234-1234-1234-123456789012",
        )

    @mock.patch('payouts.ffwd.logger.info')
    def test_unlock_splits_empty_list_passed(self, logger_mock):
        self.split1.is_owner = True
        self.split1.is_locked = True
        self.split1.save()
        self.split1.refresh_from_db()
        assert self.split1.is_locked
        FFWDHelpers.unlock_splits(self.user.id)
        self.split1.refresh_from_db()
        self.assertFalse(self.split1.is_locked)
        self.assertEqual(logger_mock.call_count, 1)
        logger_mock.assert_called_once_with(
            f"Royalty advance unlocked splits_ids=[{self.split1.pk}]"
        )

    @mock.patch('payouts.ffwd.logger.info')
    def test_unlock_splits_list_passed(self, logger_mock):
        self.split1.is_owner = True
        self.split1.is_locked = True
        self.split1.save()
        self.split1.refresh_from_db()
        assert self.split1.is_locked
        FFWDHelpers.unlock_splits(
            user_id=self.user.id, splits_to_unlock=[self.split1.pk]
        )
        self.split1.refresh_from_db()
        self.assertFalse(self.split1.is_locked)
        self.assertEqual(logger_mock.call_count, 1)
        logger_mock.assert_called_once_with(
            f"Royalty advance unlocked splits_ids=[{self.split1.pk}]"
        )

    @mock.patch("pyslayer.SlayerClient.run_in_loop")
    def test_validate_royalty_advance_offer_fail(self, validate_fn):
        validate_fn.return_value = ValidateAppRoyaltyAdvanceOfferResponse().from_dict(
            self.mocked_offer
        )
        with pytest.raises(serializers.ValidationError):
            foo = FFWDHelpers.validate_royalty_advance_offer(
                self.user.pk, self.validated_offer['royalty_advance_offer_id']
            )

    @mock.patch("pyslayer.SlayerClient.run_in_loop")
    def test_validate_royalty_advance_offer_success(self, mock_slayer):
        self.split2.song.release.status = models.Release.STATUS_RELEASED
        self.split2.song.release.save()
        self.split2.refresh_from_db()
        assert self.split2.song.release.status == models.Release.STATUS_RELEASED
        mock_slayer.return_value = ValidateAppRoyaltyAdvanceOfferResponse().from_dict(
            self.mocked_offer
        )

        return_value = FFWDHelpers.validate_royalty_advance_offer(
            self.user.pk, self.validated_offer['royalty_advance_offer_id']
        )
        self.split1.refresh_from_db()
        self.split2.refresh_from_db()
        assert self.split1.is_locked
        assert return_value == {
            'advance_id': self.mocked_offer['royalty_advance_id'],
            'raw_withdrawal_total': self.mocked_offer['withdrawal_total'],
        }

    @mock.patch("pyslayer.SlayerClient.run_in_loop")
    def test_validate_royalty_advance_offer_no_splits_success(self, mock_slayer):
        self.split2.song.release.status = models.Release.STATUS_RELEASED
        self.split2.song.release.save()
        self.split2.refresh_from_db()
        assert self.split2.song.release.status == models.Release.STATUS_RELEASED
        mock_slayer.return_value = ValidateAppRoyaltyAdvanceOfferResponse().from_dict(
            self.mocked_offer_no_splits
        )

        return_value = FFWDHelpers.validate_royalty_advance_offer(
            self.user.pk, self.validated_offer['royalty_advance_offer_id']
        )
        self.split1.refresh_from_db()
        self.split2.refresh_from_db()
        assert not self.split1.is_locked
        assert return_value == {
            'advance_id': self.mocked_offer['royalty_advance_id'],
            'raw_withdrawal_total': self.mocked_offer['withdrawal_total'],
        }
