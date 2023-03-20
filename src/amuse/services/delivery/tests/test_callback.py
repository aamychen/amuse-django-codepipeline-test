from unittest import mock
from unittest.mock import patch

import responses
from datetime import datetime, timezone

from django.test import TestCase
from django.test import override_settings
from freezegun import freeze_time

from amuse.deliveries import CHANNELS
from amuse.models.deliveries import BatchDelivery, BatchDeliveryRelease
from amuse.services.delivery.callback import (
    delivery_update_handler,
    get_taken_down_release_ids,
)

from amuse.tests.factories import BatchDeliveryFactory, BatchDeliveryReleaseFactory
from amuse.tests.helpers import (
    ZENDESK_MOCK_API_URL_TOKEN,
    add_zendesk_mock_post_response,
)
from amuse.vendor.fuga.fuga_api import FugaAPIClient
from releases.models import Release, ReleaseArtistRole
from releases.models.fuga_metadata import FugaMetadata
from releases.models.release_store_delivery_status import ReleaseStoreDeliveryStatus
from releases.tests.factories import (
    ReleaseArtistRoleFactory,
    ReleaseFactory,
    StoreFactory,
    ReleaseStoreDeliveryStatusFactory,
    FugaStoreFactory,
)
from users.tests.factories import Artistv2Factory


FUGA_TEST_SETTINGS = {
    "FUGA_API_URL": "https://fake.url/",
    "FUGA_API_USER": "test",
    "FUGA_API_PASSWORD": "test",
}

CHANNEL_MAP = dict(map(reversed, CHANNELS.items()))


@override_settings(**{**ZENDESK_MOCK_API_URL_TOKEN, **FUGA_TEST_SETTINGS})
@mock.patch("amuse.tasks.zendesk_create_or_update_user", mock.Mock())
class TestDeliveryCallback(TestCase):
    @responses.activate
    def setUp(self):
        add_zendesk_mock_post_response()
        self.release = ReleaseFactory()

        self.soundcloud = StoreFactory(
            name="Soundcloud", internal_name="soundcloud", org_id=1
        )
        self.spotify = StoreFactory(name="Spotify", internal_name="spotify", org_id=2)
        self.tiktok = StoreFactory(name="Tiktok", internal_name="tiktok", org_id=3)
        self.anghami = StoreFactory(name="Anghami", internal_name="anghami", org_id=4)
        self.apple = StoreFactory(name="Apple", internal_name="apple", org_id=5)
        self.amazon = StoreFactory(name="Amazon", internal_name="amazon", org_id=6)
        self.twitch = StoreFactory(name="Twitch", internal_name="twitch", org_id=7)
        self.facebook = StoreFactory(
            name="Facebook", internal_name="facebook", org_id=8
        )
        self.instagram = StoreFactory(
            name="Instagram", internal_name="instagram", org_id=9
        )
        self.tiktok = StoreFactory(name="Tiktok", internal_name="tiktok", org_id=10)
        self.napster = StoreFactory(name="Napster", internal_name="napster", org_id=11)
        self.shazam = StoreFactory(name="Shazam", internal_name="shazam", org_id=12)
        self.tencent = StoreFactory(name="Tencent", internal_name="tencent", org_id=13)
        self.boomplay = StoreFactory(
            name="Boomplay", internal_name="boomplay", org_id=14
        )
        self.youtube_music = StoreFactory(
            name="Youtube Music", internal_name="youtube_music", org_id=15
        )
        self.youtube_content_id = StoreFactory(
            name="Youtube CID", internal_name="youtube_content_id", org_id=16
        )
        self.fuga_deezer = FugaStoreFactory(
            name="FugaDeezer", has_delivery_service_support=True
        )
        self.deezer = StoreFactory(
            name="Deezer",
            internal_name="deezer",
            org_id=17,
            fuga_store=self.fuga_deezer,
        )

    @mock.patch("amuse.vendor.segment.events.send_release_delivered")
    def test_delivery_update_handler(self, mock_event_delivered):
        ReleaseArtistRoleFactory(
            artist=Artistv2Factory(),
            release=self.release,
            role=ReleaseArtistRole.ROLE_PRIMARY_ARTIST,
            main_primary_artist=True,
        )
        channel = CHANNEL_MAP[self.apple.internal_name]
        batch_delivery = BatchDeliveryFactory(channel=channel)
        batch_delivery_release = BatchDeliveryReleaseFactory(
            delivery=batch_delivery,
            release=self.release,
            type=BatchDeliveryRelease.DELIVERY_TYPE_INSERT,
        )

        message = {
            'delivery_id': batch_delivery.delivery_id,
            'releases': {str(self.release.pk): {'status': 'delivered', 'errors': []}},
            'status': 'delivered',
        }

        delivery_update_handler(message)
        self.release.refresh_from_db()
        batch_delivery.refresh_from_db()
        batch_delivery_release.refresh_from_db()

        assert (
            ReleaseStoreDeliveryStatus.objects.filter(
                release=self.release,
                store=self.apple,
                status=ReleaseStoreDeliveryStatus.STATUS_DELIVERED,
            ).count()
            == 1
        )

        assert batch_delivery.status == BatchDelivery.STATUS_SUCCEEDED
        assert batch_delivery_release.status == BatchDeliveryRelease.STATUS_SUCCEEDED
        assert self.release.status == Release.STATUS_DELIVERED

        mock_track_data = {
            "owner_id": self.release.user.id,
            "release_id": self.release.id,
            "release_name": self.release.name,
            "release_status": self.release.status,
            "main_primary_artist": self.release.main_primary_artist.name,
            "release_date": self.release.release_date,
            "release_flags": [],
            "songs_with_flags": [],
            "schedule_type": "static",
        }
        mock_event_delivered.assert_called_once_with(mock_track_data)

    @mock.patch("amuse.vendor.segment.events.send_release_undeliverable")
    @mock.patch("amuse.vendor.segment.events.send_release_taken_down")
    @mock.patch("amuse.vendor.segment.events.send_release_delivered")
    def test_delivery_update_handler_no_release_status_change(
        self, mock_event_delivered, mock_event_taken_down, mock_event_undeliverable
    ):
        release = ReleaseFactory(status=Release.STATUS_TAKEDOWN)
        ReleaseStoreDeliveryStatusFactory(
            release=release,
            store=self.spotify,
            status=ReleaseStoreDeliveryStatus.STATUS_TAKEDOWN,
        )
        channel = CHANNEL_MAP[self.spotify.internal_name]
        batch_delivery = BatchDeliveryFactory(channel=channel)
        batch_delivery_release = BatchDeliveryReleaseFactory(
            delivery=batch_delivery,
            release=release,
            type=BatchDeliveryRelease.DELIVERY_TYPE_TAKEDOWN,
        )

        message = {
            'delivery_id': batch_delivery.delivery_id,
            'releases': {str(release.pk): {'status': 'delivered', 'errors': []}},
            'status': 'delivered',
        }

        delivery_update_handler(message)
        release.refresh_from_db()
        batch_delivery.refresh_from_db()
        batch_delivery_release.refresh_from_db()

        assert release.status == Release.STATUS_TAKEDOWN
        assert batch_delivery.status == BatchDelivery.STATUS_SUCCEEDED
        assert batch_delivery_release.status == BatchDeliveryRelease.STATUS_SUCCEEDED

        mock_event_delivered.assert_not_called()
        mock_event_taken_down.assert_not_called()
        mock_event_undeliverable.assert_not_called()

    @mock.patch("amuse.vendor.segment.events.send_release_taken_down")
    @mock.patch("amuse.vendor.segment.events.send_release_delivered")
    def test_delivery_update_handler_updates_release_status_(
        self, mock_event_delivered, mock_event_taken_down
    ):
        release = ReleaseFactory(status=Release.STATUS_TAKEDOWN)
        ReleaseStoreDeliveryStatusFactory(
            release=release,
            store=self.spotify,
            status=ReleaseStoreDeliveryStatus.STATUS_TAKEDOWN,
        )
        channel = CHANNEL_MAP[self.spotify.internal_name]
        batch_delivery = BatchDeliveryFactory(channel=channel)
        batch_delivery_release = BatchDeliveryReleaseFactory(
            delivery=batch_delivery,
            release=release,
            type=BatchDeliveryRelease.DELIVERY_TYPE_INSERT,
        )

        message = {
            'delivery_id': batch_delivery.delivery_id,
            'releases': {str(release.pk): {'status': 'delivered', 'errors': []}},
            'status': 'delivered',
        }

        delivery_update_handler(message)
        release.refresh_from_db()
        batch_delivery.refresh_from_db()
        batch_delivery_release.refresh_from_db()

        assert release.status == Release.STATUS_DELIVERED

        mock_event_delivered.assert_called()
        mock_event_taken_down.assert_not_called()

    @mock.patch("amuse.vendor.segment.events.send_release_undeliverable")
    def test_failed_delivery_update_handler(self, mock_event_undeliverable):
        ReleaseArtistRoleFactory(
            artist=Artistv2Factory(),
            release=self.release,
            role=ReleaseArtistRole.ROLE_PRIMARY_ARTIST,
            main_primary_artist=True,
        )
        channel = CHANNEL_MAP[self.spotify.internal_name]
        batch_delivery = BatchDeliveryFactory(channel=channel)
        batch_delivery_release = BatchDeliveryReleaseFactory(
            delivery=batch_delivery, release=self.release
        )
        message = {
            'delivery_id': batch_delivery.delivery_id,
            'releases': {
                str(self.release.pk): {'status': 'failed', 'errors': [{'fail': 'fail'}]}
            },
            'status': 'failed',
        }

        delivery_update_handler(message)
        self.release.refresh_from_db()
        batch_delivery.refresh_from_db()
        batch_delivery_release.refresh_from_db()

        assert self.release.status == Release.STATUS_UNDELIVERABLE
        assert batch_delivery.status == BatchDelivery.STATUS_FAILED
        assert batch_delivery_release.status == BatchDeliveryRelease.STATUS_FAILED

        mock_track_data = {
            "owner_id": self.release.user.id,
            "release_id": self.release.id,
            "release_name": self.release.name,
            "release_status": self.release.status,
            "main_primary_artist": self.release.main_primary_artist.name,
            "release_date": self.release.release_date,
            "release_flags": [],
            "songs_with_flags": [],
            "schedule_type": "static",
        }
        mock_event_undeliverable.assert_called_once_with(mock_track_data)

        assert (
            ReleaseStoreDeliveryStatus.objects.filter(
                release=self.release, store=self.spotify
            ).count()
            == 0
        )

    @mock.patch("amuse.vendor.segment.events.send_release_taken_down")
    def test_delivery_update_handler_sets_takedown_status(self, mock_event_taken_down):
        release_1 = ReleaseFactory(status=Release.STATUS_DELIVERED)
        release_2 = ReleaseFactory(status=Release.STATUS_DELIVERED)
        ReleaseArtistRoleFactory(
            artist=Artistv2Factory(),
            release=release_2,
            role=ReleaseArtistRole.ROLE_PRIMARY_ARTIST,
            main_primary_artist=True,
        )

        batch_delivery_1 = BatchDeliveryFactory(
            channel=1, status=BatchDelivery.STATUS_SUCCEEDED, delivery_id=11
        )
        batch_delivery_2 = BatchDeliveryFactory(
            channel=2, status=BatchDelivery.STATUS_SUCCEEDED, delivery_id=22
        )
        batch_delivery_3 = BatchDeliveryFactory(channel=3, delivery_id=33)

        # Release 1 is not taken down from all stores
        batch_delivery_release_1 = BatchDeliveryReleaseFactory(
            delivery=batch_delivery_1,
            release=release_1,
            type=BatchDeliveryRelease.DELIVERY_TYPE_INSERT,
            status=BatchDeliveryRelease.STATUS_SUCCEEDED,
        )
        ReleaseStoreDeliveryStatusFactory(
            release=release_1,
            status=ReleaseStoreDeliveryStatus.STATUS_DELIVERED,
            fuga_store=self.fuga_deezer,
        )
        batch_delivery_release_2 = BatchDeliveryReleaseFactory(
            delivery=batch_delivery_2,
            release=release_1,
            type=BatchDeliveryRelease.DELIVERY_TYPE_TAKEDOWN,
            status=BatchDeliveryRelease.STATUS_SUCCEEDED,
        )
        ReleaseStoreDeliveryStatusFactory(
            release=release_1,
            status=ReleaseStoreDeliveryStatus.STATUS_TAKEDOWN,
            store=self.apple,
        )
        batch_delivery_release_3 = BatchDeliveryReleaseFactory(
            delivery=batch_delivery_3,
            release=release_1,
            type=BatchDeliveryRelease.DELIVERY_TYPE_TAKEDOWN,
        )

        # Release 2 is taken down from all stores
        batch_delivery_release_4 = BatchDeliveryReleaseFactory(
            delivery=batch_delivery_2,
            release=release_2,
            type=BatchDeliveryRelease.DELIVERY_TYPE_TAKEDOWN,
            status=BatchDeliveryRelease.STATUS_SUCCEEDED,
        )
        ReleaseStoreDeliveryStatusFactory(
            release=release_2,
            status=ReleaseStoreDeliveryStatus.STATUS_TAKEDOWN,
            store=self.apple,
        )
        batch_delivery_release_5 = BatchDeliveryReleaseFactory(
            delivery=batch_delivery_3,
            release=release_2,
            type=BatchDeliveryRelease.DELIVERY_TYPE_TAKEDOWN,
        )

        message = {
            'delivery_id': batch_delivery_3.delivery_id,
            'releases': {
                str(release_1.pk): {'status': 'delivered', 'errors': []},
                str(release_2.pk): {'status': 'delivered', 'errors': []},
            },
            'status': 'delivered',
        }

        delivery_update_handler(message)

        release_1.refresh_from_db()
        release_2.refresh_from_db()
        batch_delivery_1.refresh_from_db()
        batch_delivery_2.refresh_from_db()
        batch_delivery_release_1.refresh_from_db()
        batch_delivery_release_2.refresh_from_db()
        batch_delivery_release_3.refresh_from_db()
        batch_delivery_release_4.refresh_from_db()
        batch_delivery_release_5.refresh_from_db()

        assert release_1.status == Release.STATUS_DELIVERED
        assert release_2.status == Release.STATUS_TAKEDOWN

        assert batch_delivery_1.status == BatchDelivery.STATUS_SUCCEEDED
        assert batch_delivery_2.status == BatchDelivery.STATUS_SUCCEEDED

        assert batch_delivery_release_1.status == BatchDeliveryRelease.STATUS_SUCCEEDED
        assert batch_delivery_release_2.status == BatchDeliveryRelease.STATUS_SUCCEEDED
        assert batch_delivery_release_3.status == BatchDeliveryRelease.STATUS_SUCCEEDED
        assert batch_delivery_release_4.status == BatchDeliveryRelease.STATUS_SUCCEEDED
        assert batch_delivery_release_5.status == BatchDeliveryRelease.STATUS_SUCCEEDED

        mock_track_data = {
            "owner_id": release_2.user.id,
            "release_id": release_2.id,
            "release_name": release_2.name,
            "release_status": release_2.STATUS_DELIVERED,
            "main_primary_artist": release_2.main_primary_artist.name,
            "release_date": release_2.release_date,
            "release_flags": [],
            "songs_with_flags": [],
            "schedule_type": "static",
        }
        mock_event_taken_down.assert_called_once_with(mock_track_data)

    @mock.patch("amuse.tasks.smart_links_takedown.delay")
    @mock.patch("amuse.vendor.segment.events.send_release_taken_down")
    @patch.object(FugaAPIClient, 'delete_product', return_value=None)
    def test_delivery_update_handler_calls_fuga_delete_when_takedown_occurs(
        self, mock_fuga_delete, mock_event_taken_down, mock_smart_links
    ):
        release = ReleaseFactory(status=Release.STATUS_DELIVERED)

        fuga_metadata = FugaMetadata.objects.create(release=release, product_id=1234242)
        fuga_metadata.save()

        ReleaseArtistRoleFactory(
            artist=Artistv2Factory(),
            release=release,
            role=ReleaseArtistRole.ROLE_PRIMARY_ARTIST,
            main_primary_artist=True,
        )
        ReleaseStoreDeliveryStatusFactory(
            release=release,
            store=self.spotify,
            status=ReleaseStoreDeliveryStatus.STATUS_DELIVERED,
        )

        batch_delivery = BatchDeliveryFactory(
            channel=CHANNEL_MAP[self.spotify.internal_name], delivery_id=123123
        )
        BatchDeliveryReleaseFactory(
            delivery=batch_delivery,
            release=release,
            type=BatchDeliveryRelease.DELIVERY_TYPE_TAKEDOWN,
        )

        message = {
            'delivery_id': batch_delivery.delivery_id,
            'releases': {str(release.pk): {'status': 'delivered', 'errors': []}},
            'status': 'delivered',
        }

        delivery_update_handler(message)

        release.refresh_from_db()
        assert release.status == Release.STATUS_TAKEDOWN

        mock_event_taken_down.assert_called_once()
        mock_fuga_delete.assert_called_once_with(fuga_metadata.product_id)
        mock_smart_links.assert_called_once()

    @mock.patch("amuse.vendor.segment.events.send_release_undeliverable")
    @mock.patch("amuse.vendor.segment.events.send_release_taken_down")
    def test_delivery_update_handler_does_not_set_takedown_if_delivery_fails(
        self, mock_event_taken_down, mock_event_undeliverable
    ):
        ReleaseArtistRoleFactory(
            artist=Artistv2Factory(),
            release=self.release,
            role=ReleaseArtistRole.ROLE_PRIMARY_ARTIST,
            main_primary_artist=True,
        )
        batch_delivery_1 = BatchDeliveryFactory(
            channel=1, status=BatchDelivery.STATUS_SUCCEEDED, delivery_id=11
        )

        batch_delivery_release_1 = BatchDeliveryReleaseFactory(
            delivery=batch_delivery_1,
            release=self.release,
            type=BatchDeliveryRelease.DELIVERY_TYPE_TAKEDOWN,
            status=BatchDeliveryRelease.STATUS_SUCCEEDED,
        )

        message = {
            'delivery_id': batch_delivery_1.delivery_id,
            'releases': {str(self.release.pk): {'status': 'failed', 'errors': []}},
            'status': 'failed',
        }

        delivery_update_handler(message)

        self.release.refresh_from_db()
        batch_delivery_1.refresh_from_db()
        batch_delivery_release_1.refresh_from_db()

        assert self.release.status == Release.STATUS_UNDELIVERABLE
        assert batch_delivery_1.status == BatchDelivery.STATUS_FAILED
        assert batch_delivery_release_1.status == BatchDeliveryRelease.STATUS_FAILED

        mock_event_taken_down.assert_not_called()
        mock_track_data = {
            "owner_id": self.release.user.id,
            "release_id": self.release.id,
            "release_name": self.release.name,
            "release_status": self.release.status,
            "main_primary_artist": self.release.main_primary_artist.name,
            "release_date": self.release.release_date,
            "release_flags": [],
            "songs_with_flags": [],
            "schedule_type": "static",
        }
        mock_event_undeliverable.assert_called_once_with(mock_track_data)

    @mock.patch("amuse.vendor.segment.events.send_release_delivered")
    def test_delivery_update_handler_creates_release_store_delivery_status_when_successful_insert(
        self, _
    ):
        channel = CHANNEL_MAP[self.apple.internal_name]
        batch_delivery = BatchDeliveryFactory(channel=channel)
        batch_delivery_release = BatchDeliveryReleaseFactory(
            delivery=batch_delivery,
            release=self.release,
            type=BatchDeliveryRelease.DELIVERY_TYPE_INSERT,
        )
        message = {
            'delivery_id': batch_delivery.delivery_id,
            'releases': {str(self.release.pk): {'status': 'delivered', 'errors': []}},
            'status': 'delivered',
        }

        delivery_update_handler(message)

        assert (
            ReleaseStoreDeliveryStatus.objects.filter(
                release=self.release,
                store=self.apple,
                latest_delivery_log=batch_delivery_release,
                status=ReleaseStoreDeliveryStatus.STATUS_DELIVERED,
            ).count()
            == 1
        )

    @mock.patch("amuse.vendor.segment.events.send_release_delivered")
    def test_delivery_update_handler_creates_release_store_delivery_status_when_successful_takedown(
        self, _
    ):
        channel = CHANNEL_MAP[self.apple.internal_name]
        batch_delivery = BatchDeliveryFactory(channel=channel)
        batch_delivery_release = BatchDeliveryReleaseFactory(
            delivery=batch_delivery,
            release=self.release,
            type=BatchDeliveryRelease.DELIVERY_TYPE_TAKEDOWN,
        )
        message = {
            'delivery_id': batch_delivery.delivery_id,
            'releases': {str(self.release.pk): {'status': 'delivered', 'errors': []}},
            'status': 'delivered',
        }

        delivery_update_handler(message)

        assert (
            ReleaseStoreDeliveryStatus.objects.filter(
                release=self.release,
                store=self.apple,
                latest_delivery_log=batch_delivery_release,
                status=ReleaseStoreDeliveryStatus.STATUS_TAKEDOWN,
            ).count()
            == 1
        )

    @mock.patch("amuse.vendor.segment.events.send_release_delivered")
    def test_delivery_update_handler_creates_release_store_delivery_status_when_successful_pro_takedown(
        self, _
    ):
        channel = CHANNEL_MAP[self.apple.internal_name]
        batch_delivery = BatchDeliveryFactory(channel=channel)
        batch_delivery_release = BatchDeliveryReleaseFactory(
            delivery=batch_delivery,
            release=self.release,
            type=BatchDeliveryRelease.DELIVERY_TYPE_PRO_TAKEDOWN,
        )
        message = {
            'delivery_id': batch_delivery.delivery_id,
            'releases': {str(self.release.pk): {'status': 'delivered', 'errors': []}},
            'status': 'delivered',
        }

        delivery_update_handler(message)

        assert (
            ReleaseStoreDeliveryStatus.objects.filter(
                release=self.release,
                store=self.apple,
                latest_delivery_log=batch_delivery_release,
                status=ReleaseStoreDeliveryStatus.STATUS_TAKEDOWN,
            ).count()
            == 1
        )

    @mock.patch("amuse.vendor.segment.events.send_release_delivered")
    def test_delivery_update_handler_does_not_create_release_store_delivery_status_when_update(
        self, _
    ):
        channel = CHANNEL_MAP[self.apple.internal_name]
        batch_delivery = BatchDeliveryFactory(channel=channel)
        BatchDeliveryReleaseFactory(
            delivery=batch_delivery,
            release=self.release,
            type=BatchDeliveryRelease.DELIVERY_TYPE_UPDATE,
        )
        message = {
            'delivery_id': batch_delivery.delivery_id,
            'releases': {str(self.release.pk): {'status': 'delivered', 'errors': []}},
            'status': 'delivered',
        }

        delivery_update_handler(message)

        assert (
            ReleaseStoreDeliveryStatus.objects.filter(
                release=self.release, store=self.apple
            ).count()
            == 0
        )

    @mock.patch("amuse.vendor.segment.events.send_release_delivered")
    def test_delivery_update_handler_does_not_creates_release_store_delivery_status_when_failed(
        self, _
    ):
        channel = CHANNEL_MAP[self.apple.internal_name]
        batch_delivery = BatchDeliveryFactory(channel=channel)
        BatchDeliveryReleaseFactory(
            delivery=batch_delivery,
            release=self.release,
            type=BatchDeliveryRelease.DELIVERY_TYPE_INSERT,
        )
        message = {
            'delivery_id': batch_delivery.delivery_id,
            'releases': {str(self.release.pk): {'status': 'failed', 'errors': []}},
            'status': 'delivered',
        }

        delivery_update_handler(message)

        assert (
            ReleaseStoreDeliveryStatus.objects.filter(
                release=self.release, store=self.apple
            ).count()
            == 0
        )

    @mock.patch("amuse.vendor.segment.events.send_release_delivered")
    def test_delivery_update_handler_release_store_delivery_handles_facebook_instagram_bundling(
        self, _
    ):
        channel = CHANNEL_MAP[self.facebook.internal_name]
        batch_delivery = BatchDeliveryFactory(channel=channel)
        batch_delivery_release = BatchDeliveryReleaseFactory(
            delivery=batch_delivery,
            release=self.release,
            type=BatchDeliveryRelease.DELIVERY_TYPE_INSERT,
        )
        message = {
            'delivery_id': batch_delivery.delivery_id,
            'releases': {str(self.release.pk): {'status': 'delivered', 'errors': []}},
            'status': 'delivered',
        }

        delivery_update_handler(message)

        assert (
            ReleaseStoreDeliveryStatus.objects.filter(
                release=self.release,
                store=self.facebook,
                latest_delivery_log=batch_delivery_release,
                status=ReleaseStoreDeliveryStatus.STATUS_DELIVERED,
            ).count()
            == 1
        )
        assert (
            ReleaseStoreDeliveryStatus.objects.filter(
                release=self.release,
                store=self.instagram,
                latest_delivery_log=batch_delivery_release,
                status=ReleaseStoreDeliveryStatus.STATUS_DELIVERED,
            ).count()
            == 1
        )

    @mock.patch("amuse.vendor.segment.events.send_release_delivered")
    def test_delivery_update_handler_release_store_delivery_handles_twitch_amazon_bundling(
        self, _
    ):
        channel = CHANNEL_MAP[self.twitch.internal_name]
        batch_delivery = BatchDeliveryFactory(channel=channel)
        batch_delivery_release = BatchDeliveryReleaseFactory(
            delivery=batch_delivery,
            release=self.release,
            type=BatchDeliveryRelease.DELIVERY_TYPE_INSERT,
        )
        message = {
            'delivery_id': batch_delivery.delivery_id,
            'releases': {str(self.release.pk): {'status': 'delivered', 'errors': []}},
            'status': 'delivered',
        }

        delivery_update_handler(message)

        assert (
            ReleaseStoreDeliveryStatus.objects.filter(
                release=self.release,
                store=self.twitch,
                latest_delivery_log=batch_delivery_release,
                status=ReleaseStoreDeliveryStatus.STATUS_DELIVERED,
            ).count()
            == 1
        )
        assert (
            ReleaseStoreDeliveryStatus.objects.filter(
                release=self.release,
                store=self.amazon,
                latest_delivery_log=batch_delivery_release,
                status=ReleaseStoreDeliveryStatus.STATUS_DELIVERED,
            ).count()
            == 1
        )

    @mock.patch("amuse.vendor.segment.events.send_release_delivered")
    def test_delivery_update_handler_does_not_creates_release_store_delivery_status_for_fuga(
        self, _
    ):
        batch_delivery = BatchDeliveryFactory(channel=1)
        BatchDeliveryReleaseFactory(
            delivery=batch_delivery,
            release=self.release,
            type=BatchDeliveryRelease.DELIVERY_TYPE_INSERT,
        )
        message = {
            'delivery_id': batch_delivery.delivery_id,
            'releases': {str(self.release.pk): {'status': 'delivered', 'errors': []}},
            'status': 'delivered',
        }

        delivery_update_handler(message)

        assert (
            ReleaseStoreDeliveryStatus.objects.filter(release=self.release).count() == 0
        )

    @mock.patch("amuse.vendor.segment.events.send_release_delivered")
    def test_delivery_update_handler_updates_existing_release_store_delivery_status(
        self, _
    ):
        channel = CHANNEL_MAP[self.apple.internal_name]
        batch_delivery = BatchDeliveryFactory(channel=channel)
        BatchDeliveryReleaseFactory(
            delivery=batch_delivery,
            release=self.release,
            type=BatchDeliveryRelease.DELIVERY_TYPE_TAKEDOWN,
        )
        release_store_delivery_status = ReleaseStoreDeliveryStatus(
            release=self.release, store=self.apple, delivered_at=datetime(2020, 4, 20)
        )
        release_store_delivery_status.save()
        message = {
            'delivery_id': batch_delivery.delivery_id,
            'releases': {str(self.release.pk): {'status': 'delivered', 'errors': []}},
            'status': 'delivered',
        }

        delivery_update_handler(message)
        release_store_delivery_status.refresh_from_db()

        assert (
            ReleaseStoreDeliveryStatus.objects.filter(
                release=self.release, store=self.apple
            ).count()
            == 1
        )
        assert (
            release_store_delivery_status.status
            == ReleaseStoreDeliveryStatus.STATUS_TAKEDOWN
        )

    @mock.patch("amuse.vendor.segment.events.send_release_delivered")
    def test_delivery_update_handler_sets_release_store_delivery_status_delivered_at_time(
        self, _
    ):
        channel = CHANNEL_MAP[self.apple.internal_name]
        batch_delivery = BatchDeliveryFactory(channel=channel)
        BatchDeliveryReleaseFactory(
            delivery=batch_delivery,
            release=self.release,
            type=BatchDeliveryRelease.DELIVERY_TYPE_INSERT,
        )
        message = {
            'delivery_id': batch_delivery.delivery_id,
            'releases': {str(self.release.pk): {'status': 'delivered', 'errors': []}},
            'status': 'delivered',
        }

        # Check delivered at time set correctly when creating new entry
        with freeze_time("2020-04-30 06:00:00"):
            delivery_update_handler(message)
        release_store_delivery_status = ReleaseStoreDeliveryStatus.objects.get(
            release=self.release, store=self.apple
        )
        assert release_store_delivery_status.delivered_at == datetime(
            2020, 4, 30, 6, tzinfo=timezone.utc
        )

        # check delivered at time set correctly when updating existing entry
        with freeze_time("2020-05-28 12:00:00"):
            delivery_update_handler(message)
        release_store_delivery_status.refresh_from_db()
        assert release_store_delivery_status.delivered_at == datetime(
            2020, 5, 28, 12, tzinfo=timezone.utc
        )
