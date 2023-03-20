from datetime import date
from decimal import Decimal

import responses

from django.core.management import call_command
from django.test import TestCase, override_settings

from amuse.tests.helpers import (
    add_zendesk_mock_post_response,
    ZENDESK_MOCK_API_URL_TOKEN,
)

from releases.models import RoyaltySplit
from releases.tests.factories import RoyaltySplitFactory


@override_settings(**ZENDESK_MOCK_API_URL_TOKEN)
class BulkUpdateSplitsTestCase(TestCase):
    @responses.activate
    def setUp(self):
        add_zendesk_mock_post_response()

        self.split_to_update_1 = RoyaltySplitFactory(
            start_date=date(2020, 1, 1),
            end_date=None,
            rate=Decimal("1.00"),
            status=RoyaltySplit.STATUS_ACTIVE,
            revision=1,
        )
        self.split_to_update_2 = RoyaltySplitFactory(
            start_date=date(2020, 1, 1),
            end_date=date(2020, 2, 1),
            rate=Decimal("1.00"),
            status=RoyaltySplit.STATUS_ARCHIVED,
            revision=1,
        )
        self.split_1 = RoyaltySplitFactory(
            start_date=None,
            end_date=None,
            rate=Decimal("1.00"),
            status=RoyaltySplit.STATUS_ACTIVE,
            revision=1,
        )
        self.split_2 = RoyaltySplitFactory(
            start_date=date(2020, 1, 1),
            end_date=None,
            rate=Decimal("1.00"),
            status=RoyaltySplit.STATUS_ACTIVE,
            revision=2,
        )
        self.split_3 = RoyaltySplitFactory(
            start_date=date(2020, 1, 1),
            end_date=date(2020, 2, 1),
            rate=Decimal("1.00"),
            status=RoyaltySplit.STATUS_ARCHIVED,
            revision=3,
        )
        self.split_4 = RoyaltySplitFactory(
            user=None,
            start_date=date(2020, 2, 1),
            end_date=None,
            rate=Decimal("1.00"),
            status=RoyaltySplit.STATUS_PENDING,
            revision=2,
        )

    def test_bulk_update_splits(self):
        call_command("bulk_update_splits")

        splits = RoyaltySplit.objects.all()

        assert splits.get(id=self.split_to_update_1.id).start_date == None
        assert splits.get(id=self.split_to_update_2.id).start_date == None

        assert splits.get(id=self.split_1.id) == self.split_1
        assert splits.get(id=self.split_2.id) == self.split_2
        assert splits.get(id=self.split_3.id) == self.split_3
        assert splits.get(id=self.split_4.id) == self.split_4
