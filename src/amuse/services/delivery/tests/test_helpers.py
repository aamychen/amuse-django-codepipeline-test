from unittest import mock
from uuid import uuid4

import pytest
import responses
from django.conf import settings
from django.core.files.storage import FileSystemStorage
from django.test import TestCase
from django.test import override_settings

from amuse.models.deliveries import Batch
from amuse.services.delivery.helpers import (
    create_batch_delivery_releases_list,
    get_non_delivered_dd_stores,
    trigger_batch_delivery,
)
from amuse.services.delivery.helpers import (
    get_started_deliveries,
    mark_delivery_started,
    get_taken_down_release_ids,
)
from amuse.tasks import _calculate_django_file_checksum
from amuse.tests.helpers import (
    ZENDESK_MOCK_API_URL_TOKEN,
    add_zendesk_mock_post_response,
)
from amuse.vendor.aws import s3
from releases.models import (
    ReleaseArtistRole,
    SongArtistRole,
    SongFile,
    ReleaseStoreDeliveryStatus,
)
from releases.tests.factories import (
    CoverArtFactory,
    ReleaseArtistRoleFactory,
    ReleaseFactory,
    SongArtistRoleFactory,
    SongFactory,
    SongFileFactory,
    StoreFactory,
    FugaStoreFactory,
    ReleaseStoreDeliveryStatusFactory,
)

FUGA_TEST_SETTINGS = {
    "FUGA_API_URL": "https://fake.url/",
    "FUGA_API_USER": "test",
    "FUGA_API_PASSWORD": "test",
}


@override_settings(**{**ZENDESK_MOCK_API_URL_TOKEN, **FUGA_TEST_SETTINGS})
@mock.patch("amuse.tasks.zendesk_create_or_update_user", mock.Mock())
class TestHelpers(TestCase):
    @responses.activate
    def setUp(self):
        add_zendesk_mock_post_response()
        self.release = ReleaseFactory()
        self.soundcloud = StoreFactory(
            name="Soundcloud", internal_name="soundcloud", org_id=1
        )
        self.spotify = StoreFactory(name="Spotify", internal_name="spotify", org_id=2)
        self.amazon = StoreFactory(name="Amazon", internal_name="amazon", org_id=3)
        self.fuga_napster = FugaStoreFactory(
            name="FugaNapster", external_id=4, has_delivery_service_support=False
        )
        self.napster = StoreFactory(
            name="Napster",
            internal_name="napster",
            org_id=4,
            fuga_store=self.fuga_napster,
        )
        self.tencent = StoreFactory(name="Tencent", internal_name="tencent", org_id=5)
        self.boomplay = StoreFactory(
            name="Boomplay", internal_name="boomplay", org_id=6
        )
        self.youtube_music = StoreFactory(
            name="Youtube Music", internal_name="youtube_music", org_id=7
        )
        self.youtube_content_id = StoreFactory(
            name="Youtube CID", internal_name="youtube_content_id", org_id=8
        )
        self.deezer = StoreFactory(name="Deezer", internal_name="deezer", org_id=9)
        self.fuga_tidal = FugaStoreFactory(
            name="FugaTidal", external_id=10, has_delivery_service_support=True
        )
        self.tidal = StoreFactory(
            name="Tidal", internal_name="tidal", org_id=10, fuga_store=self.fuga_tidal
        )
        self.facebook = StoreFactory(
            name="Facebook", internal_name="facebook", org_id=11
        )
        self.instagram = StoreFactory(
            name="Instagram", internal_name="instagram", org_id=12
        )
        self.shazam = StoreFactory(
            name="Shazam",
            internal_name="shazam",
            org_id=13,
            active=False,
            admin_active=False,
        )

    def test_mark_delivery_started(self):
        release_id = uuid4()
        delivery_data = [
            {
                'release': {'id': release_id},
                'delivery': {'stores': ['fuga_store_1', 'fuga_store_2', 'soundcloud']},
            }
        ]

        mark_delivery_started(delivery_data)
        started_deliveries = get_started_deliveries(release_id)

        assert sorted(started_deliveries) == ['fuga', 'soundcloud']

    @mock.patch("amuse.services.delivery.helpers.sqs.send_message")
    @mock.patch("amuse.models.deliveries.Batch.file.field.storage", FileSystemStorage())
    def test_trigger_batch_delivery(self, mock_send_message):
        self.release.stores.set([self.spotify])

        artist_1 = self.release.user.create_artist_v2(name="Main Primary Artist")
        ReleaseArtistRoleFactory(
            release=self.release,
            artist=artist_1,
            role=ReleaseArtistRole.ROLE_PRIMARY_ARTIST,
            main_primary_artist=True,
        )
        song = SongFactory(release=self.release)
        SongFileFactory(song=song, type=SongFile.TYPE_FLAC)
        SongArtistRoleFactory(
            song=song,
            artist=artist_1,
            role=SongArtistRole.ROLE_PRIMARY_ARTIST,
            artist_sequence=1,
        )
        cover_art = CoverArtFactory(
            release=self.release, user=self.release.user, file__filename='cover.jpg'
        )

        cover_art.checksum = _calculate_django_file_checksum(cover_art.file)
        cover_art.save()

        create_batch_delivery_releases_list("insert", [self.release], True)
        releases_list = create_batch_delivery_releases_list("insert", [self.release])

        assert Batch.objects.all().count() == 0

        trigger_batch_delivery(releases_list, self.release.user)
        assert Batch.objects.all().count() == 1

        batch = Batch.objects.first()
        assert batch.status == Batch.STATUS_STARTED
        assert batch.user == self.release.user

        message = {
            "id": batch.pk,
            "file": s3.create_s3_uri(
                settings.AWS_BATCH_DELIVERY_FILE_BUCKET_NAME, batch.file.name
            ),
        }
        mock_send_message.assert_called_once_with(
            settings.RELEASE_DELIVERY_SERVICE_REQUEST_QUEUE, message
        )

    def test_trigger_batch_delivery_with_invalid_args(self):
        with pytest.raises(ValueError):
            create_batch_delivery_releases_list("insert", [], True, ["soundcloud"])

    def test_trigger_batch_delivery_with_stores(self):
        artist_1 = self.release.user.create_artist_v2(name="Main Primary Artist")
        ReleaseArtistRoleFactory(
            release=self.release,
            artist=artist_1,
            role=ReleaseArtistRole.ROLE_PRIMARY_ARTIST,
            main_primary_artist=True,
        )
        song = SongFactory(release=self.release)
        SongFileFactory(song=song, type=SongFile.TYPE_FLAC)
        SongArtistRoleFactory(
            song=song,
            artist=artist_1,
            role=SongArtistRole.ROLE_PRIMARY_ARTIST,
            artist_sequence=1,
        )
        cover_art = CoverArtFactory(
            release=self.release, user=self.release.user, file__filename='cover.jpg'
        )

        cover_art.checksum = _calculate_django_file_checksum(cover_art.file)
        cover_art.save()

        releases_list = create_batch_delivery_releases_list(
            "insert", [self.release], False, ["soundcloud"]
        )

        assert releases_list[0]["delivery"]["stores"] == ["soundcloud"]

    def test_trigger_batch_delivery_release_invalid_coverart_checksum(self):
        artist_1 = self.release.user.create_artist_v2(name="Main Primary Artist")
        ReleaseArtistRoleFactory(
            release=self.release,
            artist=artist_1,
            role=ReleaseArtistRole.ROLE_PRIMARY_ARTIST,
            main_primary_artist=True,
        )
        song = SongFactory(release=self.release)
        SongFileFactory(song=song, type=SongFile.TYPE_FLAC)
        SongArtistRoleFactory(
            song=song,
            artist=artist_1,
            role=SongArtistRole.ROLE_PRIMARY_ARTIST,
            artist_sequence=1,
        )
        cover_art = CoverArtFactory(
            release=self.release, user=self.release.user, file__filename='cover.jpg'
        )

        cover_art.checksum = 'invalid checksum'
        cover_art.save()

        with pytest.raises(ValueError):
            create_batch_delivery_releases_list(
                "insert", [self.release], False, ["soundcloud"]
            )

    def test_trigger_batch_delivery_release_missing_song_checksum(self):
        artist_1 = self.release.user.create_artist_v2(name="Main Primary Artist")
        ReleaseArtistRoleFactory(
            release=self.release,
            artist=artist_1,
            role=ReleaseArtistRole.ROLE_PRIMARY_ARTIST,
            main_primary_artist=True,
        )
        song = SongFactory(release=self.release)
        song_file = SongFileFactory(song=song, type=SongFile.TYPE_FLAC)

        # The save() actually checks for None checksum and generates a new one if None
        # so need to circumvent it by calling update instead.
        SongFile.objects.filter(pk=song_file.pk).update(checksum=None)

        SongArtistRoleFactory(
            song=song,
            artist=artist_1,
            role=SongArtistRole.ROLE_PRIMARY_ARTIST,
            artist_sequence=1,
        )
        cover_art = CoverArtFactory(
            release=self.release, user=self.release.user, file__filename='cover.jpg'
        )

        cover_art.checksum = _calculate_django_file_checksum(cover_art.file)
        cover_art.save()

        with pytest.raises(ValueError):
            create_batch_delivery_releases_list(
                "insert", [self.release], False, ["soundcloud"]
            )

    def test_trigger_batch_delivery_release_no_main_primary_artist(self):
        artist_1 = self.release.user.create_artist_v2(name="Main Primary Artist")

        # No primary release artist role
        ReleaseArtistRoleFactory(
            release=self.release,
            artist=artist_1,
            role=ReleaseArtistRole.ROLE_FEATURED_ARTIST,
            main_primary_artist=False,
        )
        song = SongFactory(release=self.release)
        SongFileFactory(song=song, type=SongFile.TYPE_FLAC)
        SongArtistRoleFactory(
            song=song,
            artist=artist_1,
            role=SongArtistRole.ROLE_PRIMARY_ARTIST,
            artist_sequence=1,
        )
        cover_art = CoverArtFactory(
            release=self.release, user=self.release.user, file__filename='cover.jpg'
        )

        cover_art.checksum = _calculate_django_file_checksum(cover_art.file)
        cover_art.save()

        with pytest.raises(AttributeError):
            create_batch_delivery_releases_list(
                "insert", [self.release], False, ["soundcloud"]
            )

    def test_trigger_batch_delivery_with_stores_bundles_fuga_fb_and_fuga_ig(self):
        artist_1 = self.release.user.create_artist_v2(name="Main Primary Artist")
        ReleaseArtistRoleFactory(
            release=self.release,
            artist=artist_1,
            role=ReleaseArtistRole.ROLE_PRIMARY_ARTIST,
            main_primary_artist=True,
        )
        song = SongFactory(release=self.release)
        SongFileFactory(song=song, type=SongFile.TYPE_FLAC)
        SongArtistRoleFactory(
            song=song,
            artist=artist_1,
            role=SongArtistRole.ROLE_PRIMARY_ARTIST,
            artist_sequence=1,
        )
        cover_art = CoverArtFactory(
            release=self.release, user=self.release.user, file__filename='cover.jpg'
        )

        cover_art.checksum = _calculate_django_file_checksum(cover_art.file)
        cover_art.save()

        releases_list = create_batch_delivery_releases_list(
            "insert", [self.release], False, ["fuga_facebook"]
        )

        assert sorted(releases_list[0]["delivery"]["stores"]) == [
            "fuga_facebook",
            "fuga_instagram",
        ]

        releases_list = create_batch_delivery_releases_list(
            "insert", [self.release], False, ["fuga_instagram"]
        )

        assert sorted(releases_list[0]["delivery"]["stores"]) == [
            "fuga_facebook",
            "fuga_instagram",
        ]

    def test_get_non_delivered_releases_with_multiple_partially_delivered_release(self):
        release_2 = ReleaseFactory()
        self.release.stores.set(
            [
                self.tidal,
                self.youtube_music,
                self.youtube_content_id,
                self.deezer,
                self.spotify,
            ]
        )
        release_2.stores.set([self.youtube_music, self.deezer, self.spotify])

        ReleaseStoreDeliveryStatusFactory(
            release=self.release,
            store=self.deezer,
            status=ReleaseStoreDeliveryStatus.STATUS_DELIVERED,
        )
        ReleaseStoreDeliveryStatusFactory(
            release=release_2,
            store=self.youtube_music,
            status=ReleaseStoreDeliveryStatus.STATUS_DELIVERED,
        )

        releases = [self.release, release_2]

        stores_releases = get_non_delivered_dd_stores(releases)

        assert dict(stores_releases) == {
            "tidal": [self.release],
            "deezer": [release_2],
            "spotify": [self.release, release_2],
            "youtube_content_id": [self.release],
            "youtube_music": [self.release],
        }

    def test_get_non_delivered_releases_with_takendown_release(self):
        self.release.stores.set(
            [
                self.tidal,
                self.youtube_music,
                self.youtube_content_id,
                self.deezer,
                self.spotify,
            ]
        )
        ReleaseStoreDeliveryStatusFactory(
            release=self.release,
            store=self.deezer,
            status=ReleaseStoreDeliveryStatus.STATUS_TAKEDOWN,
        )

        stores_releases = get_non_delivered_dd_stores([self.release])

        assert dict(stores_releases) == {}

    def test_get_non_delivered_releases_bundled_stores(self):
        release_2 = ReleaseFactory()
        self.release.stores.set([self.facebook, self.instagram])
        release_2.stores.set([self.instagram])

        stores_releases = get_non_delivered_dd_stores([self.release, release_2])

        assert dict(stores_releases) == {'facebook': [self.release, release_2]}

    def test_get_non_delivered_releases_with_fuga_delivery(self):
        self.release.stores.set([self.tidal, self.deezer])
        ReleaseStoreDeliveryStatusFactory(
            release=self.release,
            fuga_store=self.fuga_tidal,
            status=ReleaseStoreDeliveryStatus.STATUS_DELIVERED,
        )

        stores_releases = get_non_delivered_dd_stores([self.release])

        assert dict(stores_releases) == {'deezer': [self.release]}

    def test_get_taken_down_releases_still_live(self):
        live_on_fuga_release = ReleaseFactory()
        ReleaseStoreDeliveryStatusFactory(
            release=live_on_fuga_release,
            fuga_store=self.fuga_tidal,
            status=ReleaseStoreDeliveryStatus.STATUS_DELIVERED,
        )
        ReleaseStoreDeliveryStatusFactory(
            release=live_on_fuga_release,
            store=self.spotify,
            status=ReleaseStoreDeliveryStatus.STATUS_TAKEDOWN,
        )
        ReleaseStoreDeliveryStatusFactory(
            release=live_on_fuga_release,
            store=self.deezer,
            status=ReleaseStoreDeliveryStatus.STATUS_TAKEDOWN,
        )

        live_on_dd_release = ReleaseFactory()

        ReleaseStoreDeliveryStatusFactory(
            release=live_on_dd_release,
            fuga_store=self.fuga_tidal,
            status=ReleaseStoreDeliveryStatus.STATUS_TAKEDOWN,
        )
        ReleaseStoreDeliveryStatusFactory(
            release=live_on_dd_release,
            store=self.spotify,
            status=ReleaseStoreDeliveryStatus.STATUS_DELIVERED,
        )
        ReleaseStoreDeliveryStatusFactory(
            release=live_on_dd_release,
            store=self.deezer,
            status=ReleaseStoreDeliveryStatus.STATUS_TAKEDOWN,
        )

        live_release = ReleaseFactory()
        ReleaseStoreDeliveryStatusFactory(
            release=live_release,
            store=self.spotify,
            status=ReleaseStoreDeliveryStatus.STATUS_DELIVERED,
        )

        assert (
            get_taken_down_release_ids(
                [live_on_fuga_release.id, live_on_dd_release.id, live_release.id]
            )
            == []
        )

    def test_get_taken_down_releases_takendown(self):
        release = ReleaseFactory()

        ReleaseStoreDeliveryStatusFactory(
            release=release,
            fuga_store=self.fuga_tidal,
            status=ReleaseStoreDeliveryStatus.STATUS_TAKEDOWN,
        )
        ReleaseStoreDeliveryStatusFactory(
            release=release,
            store=self.spotify,
            status=ReleaseStoreDeliveryStatus.STATUS_TAKEDOWN,
        )
        ReleaseStoreDeliveryStatusFactory(
            release=release,
            store=self.deezer,
            status=ReleaseStoreDeliveryStatus.STATUS_TAKEDOWN,
        )

        # # fuga stores with has_delivery_service_support=false should be ignored
        ReleaseStoreDeliveryStatusFactory(
            release=release,
            fuga_store=self.fuga_napster,
            status=ReleaseStoreDeliveryStatus.STATUS_DELIVERED,
        )
        # # disabled stores should be ignored
        ReleaseStoreDeliveryStatusFactory(
            release=release,
            store=self.shazam,
            status=ReleaseStoreDeliveryStatus.STATUS_DELIVERED,
        )

        assert get_taken_down_release_ids([release.id]) == [release.id]
