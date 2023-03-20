from unittest.mock import patch

import responses
from django.test import TestCase, override_settings

from amuse.tests.helpers import (
    ZENDESK_MOCK_API_URL_TOKEN,
    add_zendesk_mock_post_response,
)
from amuse.vendor.fuga.fuga_api import FugaAPIClient
from releases.models import FugaStores
from releases.tests.factories import FugaMetadataFactory
import pathlib
import json

absolute_src_path = pathlib.Path(__file__).parent.parent.parent.resolve()


def load_fixture(filename):
    return open(f"{absolute_src_path}/amuse/tests/test_vendor/fixtures/{filename}")


@override_settings(**ZENDESK_MOCK_API_URL_TOKEN)
class FugaMetadataTestCase(TestCase):
    @responses.activate
    def setUp(self):
        add_zendesk_mock_post_response()
        self.fuga_metadata = FugaMetadataFactory(
            delivery_instructions_metadata=json.load(
                load_fixture("FugaDeliveryInstructions2.json")
            )
        )
        self.fuga_client = FugaAPIClient()

    @responses.activate
    @patch("releases.models.fuga_metadata.sleep")
    def test_get_and_store_metadata(self, mock_sleep):
        self.assertIsNone(self.fuga_metadata.last_parsed_at)

        self.fuga_metadata.get_and_store_metadata(self.fuga_client)

        self.fuga_metadata.refresh_from_db()
        self.assertTrue(self.fuga_metadata.last_parsed_at)

    def test_extract_stores(self):
        expected_fuga_store_ids = {
            7851192,
            103731,
            99268,
            3440259,
            2100357,
            49262307,
            1048705,
            13285026,
            1330598,
            746109,
        }
        stores = self.fuga_metadata.extract_stores()
        returned_stores_set = {store.external_id for store in stores}

        self.assertSetEqual(returned_stores_set, expected_fuga_store_ids)
        self.assertTrue(len(FugaStores.objects.all()), len(expected_fuga_store_ids))
