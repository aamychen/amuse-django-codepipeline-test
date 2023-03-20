from unittest import mock

import responses

from django.test import TestCase
from django.test import override_settings

from amuse.services.release_delivery_info import ReleaseDeliveryInfo
from amuse.tests.helpers import (
    ZENDESK_MOCK_API_URL_TOKEN,
    add_zendesk_mock_post_response,
)
from releases.models import Song, Store
from releases.tests.factories import (
    ReleaseFactory,
    SongFactory,
    StoreFactory,
    FugaStoreFactory,
    ReleaseStoreDeliveryStatusFactory,
    FugaMetadataFactory,
    FugaDeliveryHistoryFactory,
)


@override_settings(**{**ZENDESK_MOCK_API_URL_TOKEN})
@mock.patch("amuse.tasks.zendesk_create_or_update_user", mock.Mock())
class TestReleaseDeliveryInfo(TestCase):
    @responses.activate
    def setUp(self):
        add_zendesk_mock_post_response()
        self.release = ReleaseFactory()
        self.explicit_release = ReleaseFactory()
        self.explicit_song = SongFactory(
            explicit=Song.EXPLICIT_TRUE, release=self.explicit_release
        )
        self.fuga_spotify = FugaStoreFactory(
            external_id=2, name="Spotify", has_delivery_service_support=True
        )
        self.fuga_soundcloud = FugaStoreFactory(
            external_id=1, name="Soundcloud", has_delivery_service_support=True
        )
        self.fuga_non_direct_dsp = FugaStoreFactory(
            external_id=8512381238,
            name="NoDirectDeliveries",
            has_delivery_service_support=False,
        )
        self.soundcloud = StoreFactory(
            name="Soundcloud",
            internal_name="soundcloud",
            org_id=1,
            fuga_store_id=self.fuga_soundcloud.id,
        )
        self.spotify = StoreFactory(
            name="Spotify",
            internal_name="spotify",
            org_id=2,
            fuga_store_id=self.fuga_spotify.id,
        )
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
        self.youtube_content_id = StoreFactory(
            name="Youtube CID", internal_name="youtube_content_id", org_id=15
        )

    def test_store_delivery_info_includes_all_admin_active_stores(self):
        all_stores = Store.objects.filter(admin_active=True)

        release_delivery_info = ReleaseDeliveryInfo(self.release).store_delivery_info
        release_delivery_info_stores = [info['store'] for info in release_delivery_info]

        assert set(release_delivery_info_stores) == set(all_stores)

    def test_direct_delivery_insert_only_returns_selected_channels(self):
        selected_stores = [
            self.apple,
            self.shazam,
            self.spotify,
            self.soundcloud,
            self.tencent,
        ]

        self.release.stores.set(selected_stores)
        delivery_channels = ReleaseDeliveryInfo(
            self.release
        ).get_direct_delivery_channels('insert')

        assert set(delivery_channels) == set(
            [store.internal_name for store in selected_stores]
        )

    def test_direct_delivery_insert_excludes_stores_live_on_fuga(self):
        selected_stores = [self.apple, self.shazam, self.spotify, self.soundcloud]
        self.release.stores.set(selected_stores)
        ReleaseStoreDeliveryStatusFactory(
            release=self.release, fuga_store=self.fuga_spotify
        )
        ReleaseStoreDeliveryStatusFactory(
            release=self.release, fuga_store=self.fuga_non_direct_dsp
        )
        expected_stores = [self.apple, self.shazam, self.soundcloud]

        delivery_channels = ReleaseDeliveryInfo(
            self.release
        ).get_direct_delivery_channels('insert')

        assert set(delivery_channels) == set(
            [store.internal_name for store in expected_stores]
        )

    def test_direct_delivery_insert_explicit_release_excludes_non_explicit_stores(self):
        selected_stores = [self.tencent, self.shazam, self.spotify, self.soundcloud]
        self.explicit_release.stores.set(selected_stores)

        expected_stores = [self.shazam, self.spotify, self.soundcloud]

        delivery_channels = ReleaseDeliveryInfo(
            self.explicit_release
        ).get_direct_delivery_channels('insert')

        assert set(delivery_channels) == set(
            [store.internal_name for store in expected_stores]
        )

    def test_direct_delivery_insert_handles_instagram_facebook_bundling(self):
        # If both facebook and instagram only deliver to facebook
        self.release.stores.set([self.facebook, self.instagram])
        delivery_channels = ReleaseDeliveryInfo(
            self.release
        ).get_direct_delivery_channels('insert')
        assert delivery_channels == ['facebook']

        # If only instagram, deliver to facebook
        self.release.stores.set([self.instagram])
        delivery_channels = ReleaseDeliveryInfo(
            self.release
        ).get_direct_delivery_channels('insert')
        assert delivery_channels == ['facebook']

    def test_direct_delivery_insert_handles_amazon_twitch_bundling(self):
        # If both amazon and twitch, only deliver to twitch
        self.release.stores.set([self.amazon, self.twitch])
        delivery_channels = ReleaseDeliveryInfo(
            self.release
        ).get_direct_delivery_channels('insert')
        assert delivery_channels == ['twitch']

    def test_direct_delivery_update_only_stores_with_deliveries(self):
        stores = [self.spotify, self.amazon, self.tencent, self.tiktok, self.anghami]
        for store in stores:
            ReleaseStoreDeliveryStatusFactory(
                release=self.explicit_release, store=store
            )

        delivery_channels = ReleaseDeliveryInfo(
            self.explicit_release
        ).get_direct_delivery_channels('update')

        assert set(delivery_channels) == set([store.internal_name for store in stores])

    def test_direct_delivery_full_update_only_stores_with_deliveries(self):
        stores = [
            self.spotify,
            self.apple,
            self.tencent,
            self.twitch,
            self.tiktok,
            self.anghami,
        ]
        for store in stores:
            ReleaseStoreDeliveryStatusFactory(
                release=self.explicit_release, store=store
            )

        delivery_channels = ReleaseDeliveryInfo(
            self.explicit_release
        ).get_direct_delivery_channels('full_update')

        assert set(delivery_channels) == set([store.internal_name for store in stores])

    def test_direct_delivery_takedown_only_stores_with_deliveries(self):
        stores = [
            self.apple,
            self.tencent,
            self.twitch,
            self.tiktok,
            self.anghami,
            self.facebook,
            self.shazam,
        ]
        for store in stores:
            ReleaseStoreDeliveryStatusFactory(
                release=self.explicit_release, store=store
            )

        delivery_channels = ReleaseDeliveryInfo(
            self.explicit_release
        ).get_direct_delivery_channels('takedown')

        assert set(delivery_channels) == set([store.internal_name for store in stores])

    def test_direct_delivery_takedown_handles_twitch_amazon_bundling(self):
        # If delivery data for both twitch + amazon, only takedown twitch
        for store in [self.twitch, self.amazon]:
            ReleaseStoreDeliveryStatusFactory(release=self.release, store=store)

        delivery_channels = ReleaseDeliveryInfo(
            self.release
        ).get_direct_delivery_channels('takedown')

        assert delivery_channels == [self.twitch.internal_name]

    def test_direct_delivery_takedown_handles_facebook_instagram_bundling(self):
        # if both facebook and instagram, only trigger facebook
        for store in [self.facebook, self.instagram]:
            ReleaseStoreDeliveryStatusFactory(release=self.release, store=store)

        delivery_channels = ReleaseDeliveryInfo(
            self.release
        ).get_direct_delivery_channels('takedown')

        assert delivery_channels == [self.facebook.internal_name]

        # if only instagram, trigger facebook
        ReleaseStoreDeliveryStatusFactory(
            release=self.explicit_release, store=self.instagram
        )
        delivery_channels = ReleaseDeliveryInfo(
            self.explicit_release
        ).get_direct_delivery_channels('takedown')

        assert delivery_channels == [self.facebook.internal_name]

    def test_fuga_delivery_insert_returns_no_stores(self):
        selected_stores = [self.apple, self.shazam, self.spotify, self.soundcloud]
        self.release.stores.set(selected_stores)

        delivery_channels = ReleaseDeliveryInfo(
            self.release
        ).get_fuga_delivery_channels('insert')

        assert delivery_channels == []

    def test_fuga_delivery_update_returns_no_stores(self):
        selected_stores = [self.apple, self.shazam, self.spotify, self.soundcloud]
        self.release.stores.set(selected_stores)

        delivery_channels = ReleaseDeliveryInfo(
            self.release
        ).get_fuga_delivery_channels('update')

        assert delivery_channels == []

    def test_fuga_delivery_takedown_returns_only_stores_with_deliveries(self):
        self.release.stores.set([self.soundcloud])

        delivered_stores = [self.fuga_spotify, self.fuga_soundcloud]
        for store in delivered_stores:
            ReleaseStoreDeliveryStatusFactory(release=self.release, fuga_store=store)

        delivery_channels = ReleaseDeliveryInfo(
            self.release
        ).get_fuga_delivery_channels('takedown')

        assert delivery_channels == ['fuga_spotify', 'fuga_soundcloud']

    def test_fuga_delivery_full_update_returns_only_stores_with_deliveries(self):
        selected_stores = [self.apple, self.shazam, self.soundcloud]
        self.release.stores.set(selected_stores)

        delivered_stores = [self.fuga_spotify, self.fuga_soundcloud]
        for store in delivered_stores:
            ReleaseStoreDeliveryStatusFactory(release=self.release, fuga_store=store)

        delivery_channels = ReleaseDeliveryInfo(
            self.release
        ).get_fuga_delivery_channels('full_update')

        assert delivery_channels == ['fuga_spotify', 'fuga_soundcloud']

    def test_fuga_delivery_only_returns_stores_with_mapping(self):
        delivered_stores = [
            self.fuga_spotify,
            self.fuga_non_direct_dsp,
            self.fuga_soundcloud,
        ]
        for store in delivered_stores:
            ReleaseStoreDeliveryStatusFactory(release=self.release, fuga_store=store)

        delivery_channels = ReleaseDeliveryInfo(
            self.release
        ).get_fuga_delivery_channels('full_update')

        assert delivery_channels == ['fuga_spotify', 'fuga_soundcloud']

    def test_has_been_live_on_fuga_store(self):
        self.assertFalse(
            ReleaseDeliveryInfo.has_been_live_on_fuga_store(
                self.release.id, self.fuga_spotify.external_id
            )
        )
        metadata = FugaMetadataFactory(release=self.release, product_id=10)
        FugaDeliveryHistoryFactory(
            release=self.release,
            product_id=metadata.product_id,
            fuga_store=self.fuga_spotify,
            action="INSERT",
            state="DELIVERED",
        )
        self.assertTrue(
            ReleaseDeliveryInfo.has_been_live_on_fuga_store(
                self.release.id, self.fuga_spotify.external_id
            )
        )
