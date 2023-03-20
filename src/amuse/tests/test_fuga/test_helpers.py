import json
from datetime import datetime, timedelta
from unittest.mock import patch

import responses
from django.test import TestCase
from django.test import override_settings

from amuse.tests.helpers import (
    ZENDESK_MOCK_API_URL_TOKEN,
    add_zendesk_mock_post_response,
)

from amuse.vendor.fuga.helpers import sync_fuga_delivery_data
from releases.models import Release, ReleaseStoreDeliveryStatus
from releases.tests.factories import (
    FugaMetadataFactory,
    FugaStoreFactory,
    ReleaseStoreDeliveryStatusFactory,
)
from releases.tests.test_fuga_artist import load_fixture
from users.tests.factories import UserFactory


class TestFugaParser(TestCase):
    @responses.activate
    @override_settings(**ZENDESK_MOCK_API_URL_TOKEN)
    def setUp(self):
        add_zendesk_mock_post_response()
        self.fuga_release = FugaMetadataFactory(
            last_parsed_at=datetime.now() - timedelta(days=3),
            product_id=100,
            status='PUBLISHED',
        )

        self.fuga_spotify = FugaStoreFactory(name="Spotify", external_id=123)
        self.fuga_apple = FugaStoreFactory(name='Apple', external_id=324)
        self.fuga_claro_musica = FugaStoreFactory(name='iMusica', external_id=325)
        self.fuga_yt_legacy = FugaStoreFactory(
            name='YouTube Music (legacy)', external_id=326
        )
        self.user = UserFactory()

    @patch('amuse.vendor.fuga.fuga_api.FugaAPIClient.get_product_status')
    @patch('amuse.vendor.fuga.fuga_api.FugaAPIClient.get_delivery_history_for_dsp')
    @patch("amuse.vendor.fuga.fuga_api.FugaAPIClient.get_delivery_history")
    def test_sync_fuga_delivery_data_skips_sync_if_no_change_in_store_status(
        self,
        mock_get_delivery_history,
        mock_get_history_for_dsp,
        mock_get_product_status,
    ):
        ReleaseStoreDeliveryStatusFactory(
            release=self.fuga_release.release,
            fuga_store=self.fuga_apple,
            status=ReleaseStoreDeliveryStatus.STATUS_DELIVERED,
        )
        ReleaseStoreDeliveryStatusFactory(
            release=self.fuga_release.release,
            fuga_store=self.fuga_spotify,
            status=ReleaseStoreDeliveryStatus.STATUS_DELIVERED,
        )

        mock_get_delivery_history.return_value = {
            self.fuga_apple.external_id: {"state": "DELIVERED", "action": "DELIVER"},
            self.fuga_spotify.external_id: {"state": "DELIVERED", "action": "DELIVER"},
        }
        mock_get_product_status.return_value = 'PUBLISHED'

        original_parsed_at = self.fuga_release.last_parsed_at

        sync_fuga_delivery_data([self.fuga_release])
        self.fuga_release.refresh_from_db()

        assert mock_get_delivery_history.called_once_with(self.fuga_release.product_id)
        assert self.fuga_release.last_parsed_at != original_parsed_at
        assert mock_get_product_status.called_once

        # assert store sync is skipped
        assert not mock_get_history_for_dsp.called

    @patch('releases.models.fuga_metadata.FugaDeliveryHistory.sync_records_from_fuga')
    @patch('amuse.vendor.fuga.fuga_api.FugaAPIClient.get_product_status')
    @patch('amuse.vendor.fuga.fuga_api.FugaAPIClient.get_delivery_history_for_dsp')
    @patch("amuse.vendor.fuga.fuga_api.FugaAPIClient.get_delivery_history")
    def test_sync_fuga_delivery_data_syncs_if_change_in_store_status(
        self,
        mock_get_delivery_history,
        mock_get_history_for_dsp,
        mock_get_product_status,
        mock_sync_records_from_fuga,
    ):
        ReleaseStoreDeliveryStatusFactory(
            release=self.fuga_release.release,
            fuga_store=self.fuga_apple,
            status=ReleaseStoreDeliveryStatus.STATUS_DELIVERED,
        )
        ReleaseStoreDeliveryStatusFactory(
            release=self.fuga_release.release,
            fuga_store=self.fuga_spotify,
            status=ReleaseStoreDeliveryStatus.STATUS_DELIVERED,
        )

        records = json.load(load_fixture("FugaDeliveryHistory.json"))
        mock_get_history_for_dsp.return_value = records[-2:]
        mock_get_product_status.return_value = 'PUBLISHED'
        mock_get_delivery_history.return_value = {
            self.fuga_apple.external_id: {"state": "DELIVERED", "action": "DELIVER"},
            self.fuga_spotify.external_id: {"state": "DELIVERED", "action": "TAKEDOWN"},
        }
        original_parsed_at = self.fuga_release.last_parsed_at

        sync_fuga_delivery_data([self.fuga_release])
        self.fuga_release.refresh_from_db()

        # assert records are synced with fuga
        assert mock_get_delivery_history.called_once_with(self.fuga_release.product_id)
        assert self.fuga_release.last_parsed_at != original_parsed_at
        assert mock_get_history_for_dsp.called_once
        assert mock_sync_records_from_fuga.called_once
        assert mock_get_product_status.called_once

    @patch('amuse.vendor.fuga.fuga_api.FugaAPIClient.get_product_status')
    @patch('amuse.vendor.fuga.fuga_api.FugaAPIClient.get_delivery_history_for_dsp')
    @patch("amuse.vendor.fuga.fuga_api.FugaAPIClient.get_delivery_history")
    def test_sync_fuga_delivery_data_published_with_takendown_release(
        self,
        mock_get_delivery_history,
        mock_get_history_for_dsp,
        mock_get_product_status,
    ):
        self.fuga_release.release.status = Release.STATUS_TAKEDOWN
        self.fuga_release.release.save()
        ReleaseStoreDeliveryStatusFactory(
            release=self.fuga_release.release,
            fuga_store=self.fuga_apple,
            status=ReleaseStoreDeliveryStatus.STATUS_DELIVERED,
        )
        ReleaseStoreDeliveryStatusFactory(
            release=self.fuga_release.release,
            fuga_store=self.fuga_spotify,
            status=ReleaseStoreDeliveryStatus.STATUS_TAKEDOWN,
        )

        mock_get_delivery_history.return_value = {
            self.fuga_apple.external_id: {"state": "DELIVERED", "action": "INSERT"},
            self.fuga_spotify.external_id: {"state": "DELIVERED", "action": "TAKEDOWN"},
        }
        mock_get_product_status.return_value = 'PUBLISHED'

        sync_fuga_delivery_data([self.fuga_release])
        self.fuga_release.refresh_from_db()

        assert self.fuga_release.mark_to_be_deleted == True

    @patch('amuse.vendor.fuga.fuga_api.FugaAPIClient.get_product_status')
    @patch('amuse.vendor.fuga.fuga_api.FugaAPIClient.get_delivery_history_for_dsp')
    @patch("amuse.vendor.fuga.fuga_api.FugaAPIClient.get_delivery_history")
    def test_sync_fuga_delivery_data_fuga_published_with_takendown_stores(
        self,
        mock_get_delivery_history,
        mock_get_history_for_dsp,
        mock_get_product_status,
    ):
        self.fuga_release.release.status = Release.STATUS_RELEASED
        self.fuga_release.release.save()
        self.assertFalse(self.fuga_release.delete_started_at)

        ReleaseStoreDeliveryStatusFactory(
            release=self.fuga_release.release,
            fuga_store=self.fuga_claro_musica,
            status=ReleaseStoreDeliveryStatus.STATUS_DELIVERED,
        )
        ReleaseStoreDeliveryStatusFactory(
            release=self.fuga_release.release,
            fuga_store=self.fuga_yt_legacy,
            status=ReleaseStoreDeliveryStatus.STATUS_DELIVERED,
        )
        ReleaseStoreDeliveryStatusFactory(
            release=self.fuga_release.release,
            fuga_store=self.fuga_spotify,
            status=ReleaseStoreDeliveryStatus.STATUS_TAKEDOWN,
        )

        mock_get_delivery_history.return_value = {
            self.fuga_apple.external_id: {"state": "DELIVERED", "action": "TAKEDOWN"},
            self.fuga_spotify.external_id: {"state": "DELIVERED", "action": "TAKEDOWN"},
            self.fuga_claro_musica.external_id: {
                "state": "DELIVERED",
                "action": "INSERT",
            },
            self.fuga_yt_legacy.external_id: {"state": "DELIVERED", "action": "INSERT"},
        }
        mock_get_product_status.return_value = 'PUBLISHED'

        sync_fuga_delivery_data([self.fuga_release])
        self.fuga_release.refresh_from_db()
        self.assertTrue(self.fuga_release.delete_started_at)

    @patch('amuse.vendor.fuga.fuga_api.FugaAPIClient.get_product_status')
    @patch('amuse.vendor.fuga.fuga_api.FugaAPIClient.get_delivery_history_for_dsp')
    @patch("amuse.vendor.fuga.fuga_api.FugaAPIClient.get_delivery_history")
    def test_sync_fuga_delivery_data_fuga_published_with_live_stores(
        self,
        mock_get_delivery_history,
        mock_get_history_for_dsp,
        mock_get_product_status,
    ):
        self.fuga_release.release.status = Release.STATUS_RELEASED
        self.fuga_release.release.save()
        self.assertFalse(self.fuga_release.delete_started_at)

        ReleaseStoreDeliveryStatusFactory(
            release=self.fuga_release.release,
            fuga_store=self.fuga_spotify,
            status=ReleaseStoreDeliveryStatus.STATUS_DELIVERED,
        )

        mock_get_delivery_history.return_value = {
            self.fuga_spotify.external_id: {"state": "DELIVERED", "action": "INSERT"}
        }
        mock_get_product_status.return_value = 'PUBLISHED'

        sync_fuga_delivery_data([self.fuga_release])
        self.fuga_release.refresh_from_db()
        self.assertFalse(self.fuga_release.delete_started_at)
