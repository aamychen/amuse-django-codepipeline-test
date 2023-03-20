from unittest import mock

import responses
from django.test import TestCase, override_settings

from amuse import deliveries
from amuse.models.deliveries import BatchDelivery, BatchDeliveryRelease
from amuse.services.delivery.checks import FugaCheck
from amuse.tests.factories import BatchDeliveryFactory, BatchDeliveryReleaseFactory
from amuse.tests.helpers import (
    add_zendesk_mock_post_response,
    FUGA_MOCK_SETTINGS,
    ZENDESK_MOCK_API_URL_TOKEN,
)
from releases.models import Release, ReleaseStoreDeliveryStatus
from releases.tests.factories import (
    StoreFactory,
    generate_releases,
    FugaStoreFactory,
    ReleaseStoreDeliveryStatusFactory,
)


@override_settings(**{**ZENDESK_MOCK_API_URL_TOKEN, **FUGA_MOCK_SETTINGS})
class TestFugaCheck(TestCase):
    @responses.activate
    def setUp(self):
        add_zendesk_mock_post_response()
        self.release = generate_releases(1, Release.STATUS_APPROVED)[0]
        self.spotify_org_id = 10
        self.tiktok_store_id = 20
        self.fuga_spotify_store = FugaStoreFactory(name='Fuga spotify')
        self.fuga_tiktok_store = FugaStoreFactory(name='Fuga TikTok')

        self.spotify_store = StoreFactory(
            name='Spotify',
            internal_name='spotify',
            org_id=self.spotify_org_id,
            fuga_store=self.fuga_spotify_store,
        )
        self.tiktok_store = StoreFactory(
            name='Tiktok',
            internal_name='tiktok',
            org_id=self.tiktok_store_id,
            fuga_store=self.fuga_tiktok_store,
        )
        self.release.stores.add(self.spotify_store)
        self.release.stores.add(self.tiktok_store)

        ReleaseStoreDeliveryStatusFactory(
            release=self.release,
            fuga_store=self.fuga_spotify_store,
            status=ReleaseStoreDeliveryStatus.STATUS_DELIVERED,
        )

        for channel in ["fuga", "tiktok"]:
            delivery = BatchDeliveryFactory(
                status=BatchDelivery.STATUS_SUCCEEDED,
                channel=getattr(deliveries, channel.upper()),
            )
            BatchDeliveryReleaseFactory(
                status=BatchDeliveryRelease.STATUS_SUCCEEDED,
                type=BatchDeliveryRelease.DELIVERY_TYPE_INSERT,
                delivery=delivery,
                release_id=self.release.id,
            )

    def test_check_passing(self):
        check = FugaCheck(
            release=self.release, store=self.tiktok_store, operation='insert'
        )
        self.assertTrue(check.passing())

    def test_check_not_passing(self):
        check = FugaCheck(
            release=self.release, store=self.spotify_store, operation='insert'
        )
        self.assertFalse(check.passing())
