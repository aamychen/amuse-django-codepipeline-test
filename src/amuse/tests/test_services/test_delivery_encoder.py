import json
from unittest.mock import patch

import pytest
from django.conf import settings
from django.test import TestCase
from django.urls import reverse_lazy as reverse

from amuse.deliveries import APPLE, CHANNELS, TWITCH
from amuse.models.deliveries import Batch, BatchDelivery, BatchDeliveryRelease
from amuse.services.delivery.encoder import (
    release_json,
    release_asset_labels_json,
    track_asset_labels_json,
)
from amuse.tasks import _calculate_django_file_checksum
from amuse.tests.factories import (
    BatchDeliveryFactory,
    BatchDeliveryReleaseFactory,
    BatchFactory,
)
from releases.models import SongArtistRole, SongFile
from releases.tests.factories import (
    CoverArtFactory,
    ReleaseArtistRoleFactory,
    ReleaseFactory,
    SongArtistRoleFactory,
    SongFactory,
    SongFileFactory,
    StoreFactory,
)
from releases.asset_labels.builder import ReleaseAssetLabelBuilder
from users.tests.factories import UserFactory


@pytest.fixture
@patch('amuse.tasks.zendesk_create_or_update_user')
def test_release(mock_zendesk):
    release = ReleaseFactory()
    release_artist_role = ReleaseArtistRoleFactory(
        release=release, main_primary_artist=True
    )
    cover_art = CoverArtFactory(release=release)
    cover_art.checksum = _calculate_django_file_checksum(cover_art.file)
    cover_art.save()
    song = SongFactory(release=release)
    SongArtistRoleFactory(
        song=song,
        artist=release_artist_role.artist,
        role=SongArtistRole.ROLE_PRIMARY_ARTIST,
    )
    song_file = SongFileFactory(song=song, type=SongFile.TYPE_FLAC)
    return release


@pytest.mark.django_db
def test_encoder(test_release):
    assert release_json(test_release)


@pytest.mark.django_db
def test_encoder_coverart_checksum_error(test_release):
    test_release.cover_art.checksum = "FakeChecksum"
    test_release.cover_art.save()
    with pytest.raises(ValueError):
        release_json(test_release)


@pytest.mark.django_db
def test_encoder_song_empty_checksum_flag(test_release):
    song_file = test_release.songs.first().files.first()

    assert release_json(test_release, check_empty_checksum=True)
    assert release_json(test_release, check_empty_checksum=False)

    SongFile.objects.filter(pk=song_file.pk).update(checksum=None)

    with pytest.raises(ValueError):
        release_json(test_release)

    assert release_json(test_release, check_empty_checksum=False)


@pytest.mark.django_db
@patch('amuse.tasks.zendesk_create_or_update_user')
def test_artists_json(mock_zendesk):
    release = ReleaseFactory()
    cover_art = CoverArtFactory(release=release)
    cover_art.checksum = _calculate_django_file_checksum(cover_art.file)
    cover_art.save()

    main_primary_artist_role = ReleaseArtistRoleFactory(release=release)
    main_primary_artist_role.artist.spotify_id = "xxx"
    main_primary_artist_role.artist.audiomack_id = "123"
    main_primary_artist_role.artist.apple_id = "999"
    main_primary_artist_role.artist.save()

    song_1 = SongFactory(release=release)
    SongFileFactory(song=song_1, type=SongFile.TYPE_FLAC)
    artist_role_1 = SongArtistRoleFactory(
        song=song_1,
        artist=main_primary_artist_role.artist,
        role=SongArtistRole.ROLE_PRIMARY_ARTIST,
        artist_sequence=1,
    )
    artist_role_2 = SongArtistRoleFactory(
        song=song_1, artist_sequence=2, role=SongArtistRole.ROLE_PRIMARY_ARTIST
    )
    artist_role_3 = SongArtistRoleFactory(
        song=song_1, artist_sequence=3, role=SongArtistRole.ROLE_PRIMARY_ARTIST
    )

    song_2 = SongFactory(release=release)
    artist_role_4 = SongFileFactory(song=song_2, type=SongFile.TYPE_FLAC)
    artist_role_5 = SongArtistRoleFactory(
        song=song_2, artist_sequence=1, role=SongArtistRole.ROLE_PRIMARY_ARTIST
    )
    artist_role_6 = SongArtistRoleFactory(
        artist=artist_role_2.artist,
        role=SongArtistRole.ROLE_PRIMARY_ARTIST,
        song=song_2,
        artist_sequence=2,
    )
    artist_role_7 = SongArtistRoleFactory(
        artist=main_primary_artist_role.artist,
        role=SongArtistRole.ROLE_WRITER,
        song=song_2,
        artist_sequence=3,
    )
    artist_role_8 = SongArtistRoleFactory(
        artist=artist_role_2.artist,
        role=SongArtistRole.ROLE_MIXER,
        song=song_2,
        artist_sequence=4,
    )

    album_artists = [
        {
            'id': artist_role_1.artist.id,
            'name': artist_role_1.artist.name,
            'role': 'primary_artist',
            'sequence': 1,
            'spotify_id': 'xxx',
            'audiomack_id': '123',
            'apple_id': '999',
        },
        {
            'id': artist_role_2.artist.id,
            'name': artist_role_2.artist.name,
            'role': 'primary_artist',
            'sequence': 2,
            'spotify_id': None,
            'audiomack_id': None,
            'apple_id': None,
        },
    ]
    track_1_artists = [
        {
            'id': artist_role_1.artist.id,
            'name': artist_role_1.artist.name,
            'role': 'primary_artist',
            'sequence': 1,
            'spotify_id': 'xxx',
            'audiomack_id': '123',
            'apple_id': '999',
        },
        {
            'id': artist_role_2.artist.id,
            'name': artist_role_2.artist.name,
            'role': 'primary_artist',
            'sequence': 2,
            'spotify_id': None,
            'audiomack_id': None,
            'apple_id': None,
        },
        {
            'id': artist_role_3.artist.id,
            'name': artist_role_3.artist.name,
            'role': 'primary_artist',
            'sequence': 3,
            'spotify_id': None,
            'audiomack_id': None,
            'apple_id': None,
        },
    ]
    track_2_artists = [
        {
            'id': artist_role_5.artist.id,
            'name': artist_role_5.artist.name,
            'role': 'primary_artist',
            'sequence': 1,
            'spotify_id': None,
            'audiomack_id': None,
            'apple_id': None,
        },
        {
            'id': artist_role_6.artist.id,
            'name': artist_role_6.artist.name,
            'role': 'primary_artist',
            'sequence': 2,
            'spotify_id': None,
            'audiomack_id': None,
            'apple_id': None,
        },
        {
            'id': artist_role_7.artist.id,
            'name': artist_role_7.artist.name,
            'role': 'writer',
            'sequence': 3,
            'spotify_id': 'xxx',
            'audiomack_id': '123',
            'apple_id': '999',
        },
        {
            'id': artist_role_8.artist.id,
            'name': artist_role_8.artist.name,
            'role': 'mixer',
            'sequence': 4,
            'spotify_id': None,
            'audiomack_id': None,
            'apple_id': None,
        },
    ]

    payload = release_json(release)

    assert payload['artists'] == album_artists
    assert payload['tracks'][0]['artists'] == track_1_artists
    assert payload['tracks'][1]['artists'] == track_2_artists


@pytest.mark.django_db
@patch('amuse.tasks.zendesk_create_or_update_user')
def test_labels_json(mock_zendesk):
    user = UserFactory(country='SE')
    release = ReleaseFactory(user=user)
    song = SongFactory(release=release)
    r_labes_list = release_asset_labels_json(release)
    t_labels_list = track_asset_labels_json(song)
    # Assert empty list is returned if no labels are created
    assert isinstance(r_labes_list, list)
    assert isinstance(t_labels_list, list)
    assert len(r_labes_list) == 0
    assert len(t_labels_list) == 0

    # Build labels in DB and repeat test
    builder = ReleaseAssetLabelBuilder(release)
    builder.build_labels()
    r_labes_list = release_asset_labels_json(release)
    t_labels_list = track_asset_labels_json(song)
    assert isinstance(r_labes_list, list)
    assert isinstance(t_labels_list, list)
    assert len(r_labes_list) > 0
    assert len(t_labels_list) > 0
    assert "se" in t_labels_list


@pytest.mark.django_db
def test_track_id_included_in_json(test_release):
    enc = release_json(test_release)
    assert enc["tracks"][0]["id"] == test_release.songs.first().pk


@pytest.mark.django_db
def test_release_owner_user_id_included_in_json(test_release):
    enc = release_json(test_release)
    assert enc["user_id"] == test_release.user.pk


class CallbackTestCase(TestCase):
    @patch('amuse.tasks.zendesk_create_or_update_user')
    def setUp(self, mock_zd):
        self.url = reverse("sns_notification")
        self.batch = BatchFactory(status=Batch.STATUS_CREATED)
        self.releases = [ReleaseFactory() for i in range(0, 5)]

        self.store_1 = StoreFactory(internal_name="apple")
        self.store_2 = StoreFactory()
        self.store_3 = StoreFactory()

        for release in self.releases:
            release.stores.set([self.store_1, self.store_2])

    def notification(self, message):
        return json.dumps(
            {
                "Type": "Notification",
                "TopicArn": settings.RELEASE_DELIVERY_SERVICE_RESPONSE_TOPIC,
                "Message": json.dumps(message),
            }
        )

    def test_batch_update_callback(self):
        message = {
            "type": "batch_update",
            "batch_id": self.batch.id,
            "status": Batch.STATUS_OPTIONS[Batch.STATUS_STARTED],
        }

        response = self.client.post(
            self.url, self.notification(message), content_type="application/json"
        )

        self.batch.refresh_from_db()
        assert self.batch.status == Batch.STATUS_STARTED

    def test_batch_update_succeeded(self):
        message = {
            "type": "batch_update",
            "batch_id": self.batch.id,
            "status": "delivered",
        }

        response = self.client.post(
            self.url, self.notification(message), content_type="application/json"
        )

        self.batch.refresh_from_db()
        assert self.batch.status == Batch.STATUS_SUCCEEDED

    def test_delivery_created(self):
        assert not self.batch.batchdelivery_set.count()
        message = {
            "type": "delivery_created",
            "batch_id": self.batch.id,
            "delivery_id": "123456789",
            "channel": CHANNELS[APPLE],
            "releases": {
                str(release.id): {
                    "upc": release.upc.code,
                    "delivery_type": "takedown",
                    "status": "started",
                    "errors": [],
                }
                for release in self.releases
            },
        }
        response = self.client.post(
            self.url, self.notification(message), content_type="application/json"
        )
        self.batch.refresh_from_db()
        assert self.batch.batchdelivery_set.count() == 1
        batchdelivery = self.batch.batchdelivery_set.first()

        assert batchdelivery.status == BatchDelivery.STATUS_CREATED
        assert batchdelivery.releases.count() == 5

        batchdeliveryrelease = batchdelivery.batchdeliveryrelease_set.first()
        assert batchdeliveryrelease.type == BatchDeliveryRelease.DELIVERY_TYPE_TAKEDOWN

        bdr = batchdeliveryrelease
        delivery_stores = list(bdr.stores.order_by("id").values())
        release_stores = list(bdr.release.stores.order_by("id").values())

        assert delivery_stores == release_stores
        assert bdr.excluded_stores.get() == self.store_3

    def test_delivery_created_twitch(self):
        assert not self.batch.batchdelivery_set.count()

        message = {
            "type": "delivery_created",
            "batch_id": self.batch.id,
            "delivery_id": "123456789",
            "channel": CHANNELS[TWITCH],
            "releases": {
                str(release.id): {
                    "upc": release.upc.code,
                    "delivery_type": "insert",
                    "status": "started",
                    "errors": [],
                }
                for release in self.releases
            },
        }
        response = self.client.post(
            self.url, self.notification(message), content_type="application/json"
        )
        self.batch.refresh_from_db()
        assert self.batch.batchdelivery_set.count() == 1
        batchdelivery = self.batch.batchdelivery_set.first()

        assert batchdelivery.status == BatchDelivery.STATUS_CREATED
        assert batchdelivery.releases.count() == 5

        batchdeliveryrelease = batchdelivery.batchdeliveryrelease_set.first()
        assert batchdeliveryrelease.type == BatchDeliveryRelease.DELIVERY_TYPE_INSERT

        bdr = batchdeliveryrelease
        delivery_stores = list(bdr.stores.order_by("id").values())
        release_stores = list(bdr.release.stores.order_by("id").values())

        assert delivery_stores == release_stores
        assert bdr.excluded_stores.get() == self.store_3

    def test_delivery_created_save_redelivery_reference(self):
        assert not self.batch.batchdelivery_set.count()

        delivery = BatchDeliveryFactory(
            batch=self.batch, delivery_id="123456789", channel=APPLE
        )
        for release in self.releases:
            BatchDeliveryReleaseFactory(delivery=delivery, release=release)

        bdrs = BatchDeliveryRelease.objects.all()

        message = {
            "type": "delivery_created",
            "batch_id": self.batch.id,
            "delivery_id": "123456789",
            "channel": CHANNELS[APPLE],
            "releases": {
                str(bdr.release.id): {
                    "upc": bdr.release.upc.code,
                    "delivery_type": "takedown",
                    "status": "started",
                    "is_redelivery_for_bdr": bdr.id,
                    "errors": [],
                }
                for bdr in bdrs
            },
        }
        response = self.client.post(
            self.url, self.notification(message), content_type="application/json"
        )

        new_bdrs = BatchDeliveryRelease.objects.all()

        original_delivery_ids = list(
            new_bdrs.filter(redeliveries__isnull=True).values_list("id", flat=True)
        )
        redeliveries = new_bdrs.filter(redeliveries__isnull=False)

        redelivery_for_ids = [
            r.redeliveries.values_list("id", flat=True)[0] for r in redeliveries
        ]

        assert sorted(original_delivery_ids) == sorted(redelivery_for_ids)

    def test_delivery_update_succeeded(self):
        delivery = BatchDeliveryFactory(
            batch=self.batch, delivery_id="123456789", channel=APPLE
        )
        for release in self.releases:
            BatchDeliveryReleaseFactory(delivery=delivery, release=release)
        message = {
            "type": "delivery_update",
            "delivery_id": "123456789",
            "status": "succeeded",
            "releases": {
                str(release.id): {"upc": None, "status": "delivered", "errors": []}
                for release in self.releases
            },
        }
        response = self.client.post(
            self.url, self.notification(message), content_type="application/json"
        )
        delivery.refresh_from_db()
        assert delivery.status == BatchDelivery.STATUS_SUCCEEDED
        for delivery_release in delivery.batchdeliveryrelease_set.all():
            assert delivery_release.status == BatchDeliveryRelease.STATUS_SUCCEEDED
            assert delivery_release.errors == []

    def test_delivery_update_failed(self):
        delivery = BatchDeliveryFactory(
            batch=self.batch, delivery_id="123456789", channel=APPLE
        )
        for release in self.releases[:2]:
            BatchDeliveryReleaseFactory(delivery=delivery, release=release)
        message_releases = {
            str(self.releases[0].id): {"status": "failed", "errors": ["broken lmao"]},
            str(self.releases[1].id): {"status": "delivered", "errors": []},
        }
        message = {
            "type": "delivery_update",
            "delivery_id": "123456789",
            "status": "ambiguous",
            "releases": message_releases,
        }
        response = self.client.post(
            self.url, self.notification(message), content_type="application/json"
        )
        delivery.refresh_from_db()
        assert delivery.status == BatchDelivery.STATUS_AMBIGUOUS

        delivery_release0 = delivery.batchdeliveryrelease_set.get(
            release=self.releases[0]
        )
        delivery_release1 = delivery.batchdeliveryrelease_set.get(
            release=self.releases[1]
        )
        assert delivery_release0.status == BatchDeliveryRelease.STATUS_FAILED
        assert delivery_release0.errors == ["broken lmao"]
        assert delivery_release1.status == BatchDeliveryRelease.STATUS_SUCCEEDED
        assert delivery_release1.errors == []
