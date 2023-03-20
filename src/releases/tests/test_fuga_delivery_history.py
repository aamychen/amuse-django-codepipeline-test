import json
import pathlib
from unittest import mock

import responses
from django.test import TestCase, override_settings

from amuse.tests.helpers import (
    ZENDESK_MOCK_API_URL_TOKEN,
    add_zendesk_mock_post_response,
)
from releases.models import FugaDeliveryHistory
from releases.models.release_store_delivery_status import ReleaseStoreDeliveryStatus
from releases.tests.factories import (
    FugaMetadataFactory,
    FugaStoreFactory,
    FugaDeliveryHistoryFactory,
)

absolute_src_path = pathlib.Path(__file__).parent.parent.parent.resolve()


def load_fixture(filename):
    return open(f"{absolute_src_path}/amuse/tests/test_vendor/fixtures/{filename}")


@override_settings(**ZENDESK_MOCK_API_URL_TOKEN)
@mock.patch("amuse.tasks.zendesk_create_or_update_user", mock.Mock())
class FugaDeliveryHistoryTestCase(TestCase):
    @responses.activate
    def setUp(self):
        add_zendesk_mock_post_response()
        self.fuga_metadata = FugaMetadataFactory(product_id=2165610288)
        self.fuga_store = FugaStoreFactory(external_id=1, name="Anghami")

    def test_delete_previous_records(self):
        FugaDeliveryHistoryFactory(
            product_id=self.fuga_metadata.product_id, fuga_store=self.fuga_store
        )
        records = FugaDeliveryHistory.objects.filter(
            product_id=self.fuga_metadata.product_id, fuga_store=self.fuga_store
        )
        self.assertEqual(len(records), 1)
        FugaDeliveryHistory.delete_previous_records(self.fuga_metadata, self.fuga_store)
        records = FugaDeliveryHistory.objects.filter(
            product_id=self.fuga_metadata.product_id, fuga_store=self.fuga_store
        )
        self.assertEqual(len(records), 0)

    def test_parse_fuga_delivery_feed_for_dsp(self):
        records = json.load(load_fixture("FugaDeliveryHistory.json"))
        FugaDeliveryHistory.parse_fuga_delivery_feed_for_dsp(
            self.fuga_metadata, self.fuga_store, records
        )
        self.assertEqual(
            len(
                FugaDeliveryHistory.objects.filter(
                    product_id=self.fuga_metadata.product_id
                )
            ),
            4,
        )

    def test_parse_fuga_delivery_feed_for_dsp_without_user(self):
        records = json.load(load_fixture("FugaDeliveryHistoryWithoutUser.json"))
        FugaDeliveryHistory.parse_fuga_delivery_feed_for_dsp(
            self.fuga_metadata, self.fuga_store, records
        )
        fuga_history_records = FugaDeliveryHistory.objects.filter(
            product_id=self.fuga_metadata.product_id
        )
        self.assertEqual(len(fuga_history_records), 1)
        self.assertIsNone(fuga_history_records[0].executed_by)

    def test_parse_fuga_delivery_feed_for_dsp_with_user(self):
        records = json.load(load_fixture("FugaDeliveryHistoryWithUser.json"))
        FugaDeliveryHistory.parse_fuga_delivery_feed_for_dsp(
            self.fuga_metadata, self.fuga_store, records
        )
        fuga_history_records = FugaDeliveryHistory.objects.filter(
            product_id=self.fuga_metadata.product_id
        )
        self.assertEqual(len(fuga_history_records), 1)
        self.assertEqual(fuga_history_records[0].executed_by, "Bulk Admin")

    def test_get_new_records(self):
        records = json.load(load_fixture("FugaDeliveryHistory.json"))
        self.assertEqual(len(records), 4)

        # Precondition - We have 2 records in the database out of 4 fetched ones
        FugaDeliveryHistory.parse_fuga_delivery_feed_for_dsp(
            self.fuga_metadata, self.fuga_store, records[-2:]
        )

        # Get the new latest records that have not been stored
        new_records = FugaDeliveryHistory.get_new_records(
            self.fuga_metadata, self.fuga_store, records
        )

        # Verify
        self.assertEqual(len(new_records), 2)

    def test_sync_records_from_fuga(self):
        records = json.load(load_fixture("FugaDeliveryHistory.json"))
        self.assertEqual(len(records), 4)

        # Simulate parsing after insert
        FugaDeliveryHistory.sync_records_from_fuga(
            self.fuga_metadata, self.fuga_store, records[-2:]
        )
        historical_records = FugaDeliveryHistory.objects.filter(
            release=self.fuga_metadata.release.id, fuga_store=self.fuga_store
        )
        delivery_status = ReleaseStoreDeliveryStatus.objects.get(
            release_id=self.fuga_metadata.release.id, fuga_store=self.fuga_store
        )
        self.assertEqual(len(historical_records), 2)
        self.assertEqual(
            delivery_status.status, ReleaseStoreDeliveryStatus.STATUS_DELIVERED
        )

        # Simulate parsing after insert and subsequent takedown
        FugaDeliveryHistory.sync_records_from_fuga(
            self.fuga_metadata, self.fuga_store, records
        )
        historical_records = FugaDeliveryHistory.objects.filter(
            release=self.fuga_metadata.release.id, fuga_store=self.fuga_store
        )
        delivery_status = ReleaseStoreDeliveryStatus.objects.get(
            release_id=self.fuga_metadata.release.id, fuga_store=self.fuga_store
        )
        self.assertEqual(len(historical_records), 4)
        self.assertEqual(
            delivery_status.status, ReleaseStoreDeliveryStatus.STATUS_TAKEDOWN
        )
