import json
import pathlib
from datetime import datetime, timedelta
from unittest.mock import patch

import responses
from django.conf import settings
from django.test import TestCase
from django.test import override_settings

from amuse.tests.helpers import (
    ZENDESK_MOCK_API_URL_TOKEN,
    add_zendesk_mock_post_response,
)
from amuse.vendor.fuga.cronjob import (
    parse_releases_from_fuga,
    parse_dsp_history_from_fuga,
    sync_fuga_releases,
    fuga_spotify_direct_deliver,
    _fuga_spotify_direct_deliver_batch,
    fuga_spotify_takedown,
)
from releases.models import Release
from releases.tests.factories import (
    FugaMetadataFactory,
    FugaStoreFactory,
    FugaArtistFactory,
    StoreFactory,
    ReleaseStoreDeliveryStatusFactory,
)
from users.tests.factories import UserFactory

absolute_src_path = pathlib.Path(__file__).parent.parent.resolve()


def load_fixture(filename):
    return open(f"{absolute_src_path}/test_vendor/fixtures/{filename}")


class TestFugaParser(TestCase):
    @responses.activate
    @override_settings(**ZENDESK_MOCK_API_URL_TOKEN)
    def setUp(self):
        add_zendesk_mock_post_response()
        self.fuga_unparsed_release = FugaMetadataFactory()
        self.fuga_parsed_release = FugaMetadataFactory(
            last_parsed_at=datetime.now(), product_id=100
        )
        self.fuga_store = FugaStoreFactory(name="Spotify", external_id=123)
        self.fuga_artist = FugaArtistFactory()
        self.store = StoreFactory(
            name="Spotify",
            internal_name="spotify",
            batch_size=1,
            fuga_store=self.fuga_store,
        )
        self.user = UserFactory(email="filotas@amuse.io", first_name="Filotas")

    @patch("releases.models.fuga_metadata.FugaMetadata.get_and_store_metadata")
    def test_parse(self, mock_get_and_store_metadata):
        parse_releases_from_fuga()
        mock_get_and_store_metadata.assert_called_once()

    @patch(
        "releases.models.fuga_metadata.FugaDeliveryHistory.parse_fuga_delivery_feed_for_dsp"
    )
    def test_parse_dsp_history_from_fuga(self, mock_parse_fuga_feed_for_dsp):
        self.assertIsNone(self.fuga_unparsed_release.delivery_history_extracted_at)
        self.assertIsNone(self.fuga_parsed_release.delivery_history_extracted_at)
        with patch(
            "releases.models.fuga_metadata.FugaMetadata.extract_stores",
            return_value=[self.fuga_store],
        ):
            parse_dsp_history_from_fuga()
        mock_parse_fuga_feed_for_dsp.assert_called_once()
        self.fuga_parsed_release.refresh_from_db()
        self.fuga_unparsed_release.refresh_from_db()
        self.assertIsNone(self.fuga_unparsed_release.delivery_history_extracted_at)
        self.assertTrue(self.fuga_parsed_release.delivery_history_extracted_at)

    @patch(
        "amuse.vendor.fuga.fuga_api.FugaAPIClient.get_delivery_history", return_value={}
    )
    @patch("releases.models.fuga_metadata.FugaMetadata.extract_stores", return_value=[])
    @patch("amuse.vendor.fuga.helpers.segment_release_taken_down")
    @patch(
        "amuse.vendor.fuga.fuga_api.FugaAPIClient.get_product_status",
        return_value="DELETED",
    )
    def test_sync_fuga_releases_confirm_deleted(
        self, mock_get_product_status, mock_segment_takedown, _mock, _mock2
    ):
        self.fuga_parsed_release.delete_started_at = datetime.now() - timedelta(hours=2)
        self.fuga_parsed_release.release.status = Release.STATUS_RELEASED
        self.fuga_parsed_release.release.save()
        self.fuga_parsed_release.save()

        self.assertEqual(self.fuga_parsed_release.status, "PUBLISHED")

        sync_fuga_releases(confirm_deleted=True)

        self.fuga_parsed_release.refresh_from_db()
        self.assertEqual(self.fuga_parsed_release.status, "DELETED")

        mock_get_product_status.assert_called_once()
        mock_segment_takedown.assert_called_once_with(self.fuga_parsed_release.release)

        self.assertEqual(
            self.fuga_parsed_release.release.status, Release.STATUS_TAKEDOWN
        )

    @patch("amuse.vendor.fuga.cronjob.deliver_batches")
    def test_fuga_spotify_direct_deliver_batch(self, mock_deliver_batches):
        # Pre-conditions
        self.assertFalse(self.fuga_parsed_release.spotify_migration_started_at)
        self.assertFalse(self.store in self.fuga_parsed_release.release.stores.all())

        # Under test
        fuga_releases = [self.fuga_parsed_release]
        _fuga_spotify_direct_deliver_batch(fuga_releases, self.store, self.user)
        self.fuga_parsed_release.refresh_from_db()

        # Assert post-conditions
        mock_deliver_batches.assert_called_once()
        self.assertTrue(self.store in self.fuga_parsed_release.release.stores.all())
        self.assertTrue(self.fuga_parsed_release.spotify_migration_started_at)

    @patch("amuse.vendor.fuga.cronjob._fuga_spotify_direct_deliver_batch")
    def test_fuga_spotify_direct_deliver_whitelisted(self, mock_direct_delivery):
        # Pre-conditions
        self.fuga_parsed_release.ready_to_migrate = True
        self.fuga_parsed_release.spotify_ready_to_migrate = True
        self.fuga_parsed_release.whitelisted = True
        self.fuga_parsed_release.save()

        # Under test
        fuga_spotify_direct_deliver(user_id=self.user.id)

        # Assert post-conditions
        mock_direct_delivery.assert_not_called()

    @patch("amuse.vendor.fuga.cronjob._fuga_spotify_direct_deliver_batch")
    def test_fuga_spotify_direct_deliver_migration_already_started(
        self, mock_direct_delivery
    ):
        # Pre-conditions
        self.fuga_parsed_release.ready_to_migrate = True
        self.fuga_parsed_release.spotify_ready_to_migrate = True
        self.fuga_parsed_release.spotify_migration_started_at = datetime.now()
        self.fuga_parsed_release.save()

        # Under test
        fuga_spotify_direct_deliver(user_id=self.user.id)

        # Assert post-conditions
        mock_direct_delivery.assert_not_called()

    @patch("amuse.vendor.fuga.cronjob._fuga_spotify_direct_deliver_batch")
    def test_fuga_spotify_direct_deliver_takendown_release(self, mock_direct_delivery):
        # Pre-conditions
        self.fuga_parsed_release.ready_to_migrate = True
        self.fuga_parsed_release.spotify_ready_to_migrate = True
        self.fuga_parsed_release.save()
        self.fuga_parsed_release.release.status = Release.STATUS_TAKEDOWN
        self.fuga_parsed_release.release.save()

        # Under test
        fuga_spotify_direct_deliver(user_id=self.user.id)
        self.fuga_parsed_release.refresh_from_db()

        # Assert post-conditions
        mock_direct_delivery.assert_not_called()
        self.assertFalse(self.fuga_parsed_release.spotify_ready_to_migrate)
        self.assertFalse(self.fuga_parsed_release.ready_to_migrate)

    @patch(
        "amuse.vendor.fuga.fuga_api.FugaAPIClient.get_delivery_history_for_dsp",
        return_value=[],
    )
    @patch("amuse.vendor.fuga.cronjob._fuga_spotify_direct_deliver_batch")
    def test_fuga_spotify_direct_deliver_no_fuga_history(
        self, mock_direct_delivery, mock_get_delivery_history
    ):
        # Pre-conditions
        self.fuga_parsed_release.ready_to_migrate = True
        self.fuga_parsed_release.spotify_ready_to_migrate = True
        self.fuga_parsed_release.save()

        # Under test
        fuga_spotify_direct_deliver(user_id=self.user.id)
        self.fuga_parsed_release.refresh_from_db()

        # Assert post-conditions
        mock_get_delivery_history.assert_called_once()
        mock_direct_delivery.assert_not_called()
        self.assertFalse(self.fuga_parsed_release.spotify_ready_to_migrate)

    @responses.activate
    @override_settings(
        FUGA_API_URL="https://fake.url/", FUGA_API_USER="test", FUGA_API_PASSWORD="test"
    )
    @patch("amuse.vendor.fuga.cronjob._fuga_spotify_direct_deliver_batch")
    def test_fuga_spotify_direct_deliver_with_fuga_history(self, mock_direct_delivery):
        # Pre-conditions
        cookie_string = "magic-fake-cookie-string"
        self.fuga_parsed_release.ready_to_migrate = True
        self.fuga_parsed_release.spotify_ready_to_migrate = True
        self.fuga_parsed_release.save()

        responses.add(
            responses.POST,
            settings.FUGA_API_URL + "login",
            headers={"Set-Cookie": "connect.sid=%s;" % cookie_string},
            status=200,
        )
        responses.add(
            responses.GET,
            settings.FUGA_API_URL
            + "v2/products/%s/delivery_instructions/%s/history"
            % (self.fuga_parsed_release.product_id, self.fuga_store.external_id),
            json=json.load(load_fixture("FugaDeliveryHistorySpotify.json")),
            status=200,
        )

        # Under test
        fuga_spotify_direct_deliver(user_id=self.user.id)
        self.fuga_parsed_release.refresh_from_db()

        # Assert post-conditions
        mock_direct_delivery.assert_called_once()

    @patch(
        "amuse.vendor.fuga.fuga_api.FugaAPIClient.post_product_takedown",
        return_value=[],
    )
    def test_fuga_spotify_takedown(self, mock_product_takedown):
        # Pre-conditions
        cookie_string = "magic-fake-cookie-string"
        self.fuga_parsed_release.ready_to_migrate = True
        self.fuga_parsed_release.spotify_ready_to_migrate = True
        self.fuga_parsed_release.spotify_migration_started_at = (
            datetime.now() - timedelta(days=8)
        )
        self.fuga_parsed_release.save()

        ReleaseStoreDeliveryStatusFactory(
            release=self.fuga_parsed_release.release, store=self.store
        )

        # Under test
        fuga_spotify_takedown()
        self.fuga_parsed_release.refresh_from_db()

        # Assert post-conditions
        mock_product_takedown.assert_called_once()
        self.assertTrue(self.fuga_parsed_release.spotify_migration_started_at)
        self.assertTrue(self.fuga_parsed_release.spotify_migration_completed_at)
