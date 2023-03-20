from datetime import datetime
from unittest import mock

from django.core.management import call_command
from django.test import TestCase
from freezegun import freeze_time

from amuse.deliveries import FUGA, SOUNDCLOUD, TIKTOK, SPOTIFY
from amuse.models.deliveries import BatchDelivery, BatchDeliveryRelease
from amuse.tasks import _calculate_django_file_checksum
from amuse.tests.factories import (
    BatchFactory,
    BatchDeliveryFactory,
    BatchDeliveryReleaseFactory,
    SupportReleaseFactory,
)
from amuse.tests.test_utils import patch_func
from releases.models import (
    Release,
    SongFile,
    SongArtistRole,
    ReleaseArtistRole,
    ReleaseStoreDeliveryStatus,
)
from releases.tests.factories import (
    ReleaseFactory,
    StoreFactory,
    CoverArtFactory,
    ReleaseArtistRoleFactory,
    SongFactory,
    SongFileFactory,
    SongArtistRoleFactory,
    FugaStoreFactory,
    ReleaseStoreDeliveryStatusFactory,
)
from users.tests.factories import UserFactory

CREATE_BATCH_DELIVERY_PATH = (
    "amuse.services.delivery.helpers.create_batch_delivery_releases_list"
)
TRIGGER_BATCH_DELIVERY_PATH = "amuse.services.delivery.helpers.trigger_batch_delivery"
SLEEP_PATH = "amuse.services.delivery.helpers.sleep"


class TriggerDeliveryTestCase(TestCase):
    def setUp(self):
        patch_func(self, "amuse.tasks.send_email_verification_email", "mock_email")
        patch_func(self, "amuse.tasks.zendesk_create_or_update_user", "mock_zendesk")
        patch_func(self, "amuse.tasks.post_slack_user_created", "mock_user_created")
        patch_func(
            self, "amuse.tasks.post_slack_release_created", "mock_release_created"
        )

        self.fuga_napster = FugaStoreFactory(
            name="fuga_napster", has_delivery_service_support=True
        )
        self.store_napster = StoreFactory(
            internal_name="napster", org_id=0, fuga_store=self.fuga_napster
        )
        self.store_youtube_music = StoreFactory(internal_name="youtube_music", org_id=1)
        self.store_youtube_content_id = StoreFactory(
            internal_name="youtube_content_id", org_id=2
        )
        self.store_deezer = StoreFactory(internal_name="deezer", org_id=3)
        self.store_spotify = StoreFactory(internal_name="spotify", org_id=4)
        self.store_shazam = StoreFactory(internal_name="shazam", org_id=5)
        self.store_tiktok = StoreFactory(internal_name="tiktok", org_id=6)
        self.store_amazon = StoreFactory(internal_name="amazon", org_id=7)
        self.store_twitch = StoreFactory(internal_name="twitch", org_id=8)
        self.store_soundcloud = StoreFactory(internal_name="soundcloud", org_id=9)

    @mock.patch(CREATE_BATCH_DELIVERY_PATH, return_value=10)
    @mock.patch(TRIGGER_BATCH_DELIVERY_PATH, return_value=999)
    def test_deliver_release_ids(self, mock_trigger_batch, mock_create_batch):
        for i in range(2):
            ReleaseFactory()

        release = Release.objects.first()
        release.status = Release.STATUS_APPROVED
        release.save()

        user = UserFactory()

        call_command(
            "trigger_delivery",
            "--release_ids=%s" % (release.pk),
            "--type=insert",
            f"--user_id={user.id}",
        )

        mock_create_batch.assert_called_with(
            delivery_type="insert",
            only_fuga=False,
            releases=[release],
            override_stores=False,
            stores=[],
        )
        mock_trigger_batch.assert_called_with(mock_create_batch.return_value, user)

        assert mock_create_batch.call_count == 1
        assert mock_trigger_batch.call_count == 1

    @mock.patch(SLEEP_PATH)
    @mock.patch(CREATE_BATCH_DELIVERY_PATH)
    @mock.patch(TRIGGER_BATCH_DELIVERY_PATH, return_value=999)
    def test_deliver_override_stores(
        self, mock_trigger_batch, mock_create_batch, mock_sleep
    ):
        for i in range(2):
            ReleaseFactory()

        release = Release.objects.first()
        release.status = Release.STATUS_APPROVED
        release.save()

        call_command(
            "trigger_delivery",
            "--release_ids=%s" % release.pk,
            "--type=insert",
            "--override_stores",
        )

        mock_create_batch.assert_called_with(
            delivery_type="insert",
            only_fuga=False,
            releases=[release],
            override_stores=True,
            stores=[],
        )
        mock_trigger_batch.assert_called()

        assert mock_create_batch.call_count == 1
        assert mock_trigger_batch.call_count == 1

    @mock.patch(SLEEP_PATH)
    @mock.patch(CREATE_BATCH_DELIVERY_PATH)
    @mock.patch(TRIGGER_BATCH_DELIVERY_PATH, return_value=999)
    def test_deliver_stores(self, mock_trigger_batch, mock_create_batch, mock_sleep):
        for i in range(2):
            ReleaseFactory()

        release = Release.objects.first()
        release.status = Release.STATUS_APPROVED
        release.stores.add(self.store_soundcloud)
        release.save()

        call_command(
            "trigger_delivery",
            "--release_ids=%s" % release.pk,
            "--type=takedown",
            "--stores=soundcloud",
        )

        mock_create_batch.assert_called_with(
            delivery_type="takedown",
            only_fuga=False,
            releases=[release],
            override_stores=False,
            stores=["soundcloud"],
        )
        mock_trigger_batch.assert_called()

        assert mock_create_batch.call_count == 1
        assert mock_trigger_batch.call_count == 1

    @mock.patch(SLEEP_PATH)
    @mock.patch(CREATE_BATCH_DELIVERY_PATH)
    @mock.patch(TRIGGER_BATCH_DELIVERY_PATH, return_value=999)
    def test_deliver_skip_not_included_stores(
        self, mock_trigger_batch, mock_create_batch, mock_sleep
    ):
        for i in range(2):
            ReleaseFactory()

        release = Release.objects.first()
        release.status = Release.STATUS_APPROVED
        release.save()

        call_command(
            "trigger_delivery",
            "--release_ids=%s" % release.pk,
            "--type=takedown",
            "--stores=soundcloud",
        )

        mock_create_batch.assert_not_called()
        mock_trigger_batch.assert_not_called()

    @mock.patch(SLEEP_PATH)
    @mock.patch(CREATE_BATCH_DELIVERY_PATH)
    @mock.patch(TRIGGER_BATCH_DELIVERY_PATH, return_value=999)
    def test_deliver_dryrun(self, mock_trigger_batch, mock_create_batch, mock_sleep):
        for i in range(2):
            ReleaseFactory()

        release = Release.objects.first()
        release.status = Release.STATUS_APPROVED
        release.save()

        call_command(
            "trigger_delivery",
            "--release_ids=%s" % release.pk,
            "--type=takedown",
            "--dryrun",
        )

        mock_create_batch.assert_not_called()
        mock_trigger_batch.assert_not_called()

    @mock.patch(SLEEP_PATH)
    @mock.patch(CREATE_BATCH_DELIVERY_PATH)
    @mock.patch(TRIGGER_BATCH_DELIVERY_PATH, return_value=999)
    def test_deliver_batchsize_delay(
        self, mock_trigger_batch, mock_create_batch, mock_sleep
    ):
        for i in range(10):
            ReleaseFactory()

        releases = Release.objects.all()
        releases.update(status=Release.STATUS_APPROVED)

        delay = 0.1

        call_command(
            "trigger_delivery",
            "--type=insert",
            "--batchsize=3",
            "--delay=%s" % delay,
            **{"release_ids": list(releases.values_list("pk", flat=True))},
        )

        assert mock_trigger_batch.call_count == 4
        assert mock_create_batch.call_count == 4

        mock_sleep.assert_called_with(delay)
        assert mock_sleep.call_count == 4

    @mock.patch(SLEEP_PATH)
    @mock.patch(CREATE_BATCH_DELIVERY_PATH)
    @mock.patch(TRIGGER_BATCH_DELIVERY_PATH, return_value=999)
    def test_deliver_status(self, mock_trigger_batch, mock_create_batch, mock_sleep):
        for i in range(2):
            ReleaseFactory()

        releases = Release.objects.all()
        first_release = releases.first()
        first_release.status = Release.STATUS_UNDELIVERABLE
        first_release.save()

        call_command(
            "trigger_delivery",
            "--release_ids=%s" % first_release.pk,
            "--type=insert",
            "--status=%s" % Release.STATUS_UNDELIVERABLE,
        )

        assert mock_trigger_batch.call_count == 1
        assert mock_create_batch.call_count == 1
        assert mock_sleep.call_count == 1

    @mock.patch(SLEEP_PATH)
    @mock.patch(CREATE_BATCH_DELIVERY_PATH, return_value=112)
    @mock.patch(TRIGGER_BATCH_DELIVERY_PATH, return_value=999)
    def test_redelivery(self, mock_trigger_batch, mock_create_batch, mock_sleep):
        for i in range(3):
            ReleaseFactory()

        releases = Release.objects.all()

        for release in releases:
            batch = BatchFactory()
            delivery = BatchDeliveryFactory(channel=SOUNDCLOUD, batch=batch)
            BatchDeliveryReleaseFactory(
                release=release,
                delivery=delivery,
                status=BatchDeliveryRelease.STATUS_SUCCEEDED,
            )

        bdr = BatchDeliveryRelease.objects.all().order_by("id")
        bdr_ids = list(bdr.values_list("id", flat=True))

        bdr_1 = bdr[0]
        bdr_2 = bdr[1]
        bdr_3 = bdr[2]

        bdr_1.delivery.channel = TIKTOK
        bdr_1.type = BatchDeliveryRelease.DELIVERY_TYPE_UPDATE
        bdr_1.redeliver = True
        bdr_1.delivery.save()
        bdr_1.save()

        bdr_2.delivery.channel = SOUNDCLOUD
        bdr_2.type = BatchDeliveryRelease.DELIVERY_TYPE_TAKEDOWN
        bdr_2.redeliver = True
        bdr_2.delivery.save()
        bdr_2.save()

        bdr_3.delivery.channel = TIKTOK
        bdr_3.type = BatchDeliveryRelease.DELIVERY_TYPE_TAKEDOWN
        bdr_3.redeliver = True
        bdr_3.delivery.save()
        bdr_3.save()

        user = UserFactory()

        call_command(
            "trigger_redelivery",
            "--batchsize=1",
            "--delay=0",
            f"--user_id={user.id}",
            "--limit=2",
        )

        assert mock_trigger_batch.call_count == 2

        mock_trigger_batch.assert_has_calls(
            [
                mock.call(mock_create_batch.return_value, user),
                mock.call(mock_create_batch.return_value, user),
            ]
        )

        mock_create_batch.assert_has_calls(
            [
                mock.call(
                    delivery_type="update",
                    only_fuga=False,
                    override_stores=False,
                    releases=[bdr_1.release],
                    stores=["tiktok"],
                ),
                mock.call(
                    delivery_type="takedown",
                    only_fuga=False,
                    override_stores=False,
                    releases=[bdr_2.release],
                    stores=["soundcloud"],
                ),
            ]
        )

        mock_sleep.assert_called_with(0)
        assert mock_sleep.call_count == 2

        bdr_1.refresh_from_db()
        bdr_2.refresh_from_db()

        assert bdr_1.redeliver is False and bdr_2.redeliver is False
        assert bdr_1.status == BatchDeliveryRelease.STATUS_REDELIVERED
        assert bdr_2.status == BatchDeliveryRelease.STATUS_REDELIVERED

    @mock.patch(SLEEP_PATH)
    @mock.patch("amuse.services.delivery.helpers.release_json")
    @mock.patch(TRIGGER_BATCH_DELIVERY_PATH)
    def test_fuga_redelivery_insert(
        self, mock_trigger_batch, mock_release_json, mock_sleep
    ):
        for i in range(3):
            ReleaseFactory()

        mock_trigger_batch.return_value = 999
        mock_release_json.return_value = {}

        release = Release.objects.first()
        release.stores.add(
            self.store_shazam, self.store_napster, self.store_tiktok, self.store_spotify
        )

        release_2 = Release.objects.last()
        release_2.stores.add(self.store_napster, self.store_tiktok, self.store_spotify)

        delivery = BatchDeliveryFactory(channel=FUGA)
        bdr = BatchDeliveryReleaseFactory(
            release=release,
            delivery=delivery,
            type=BatchDeliveryRelease.DELIVERY_TYPE_INSERT,
            status=BatchDeliveryRelease.STATUS_CREATED,
            redeliver=True,
        )
        delivery_2 = BatchDeliveryFactory(channel=FUGA)
        bdr_2 = BatchDeliveryReleaseFactory(
            release=release_2,
            delivery=delivery,
            type=BatchDeliveryRelease.DELIVERY_TYPE_INSERT,
            status=BatchDeliveryRelease.STATUS_CREATED,
            redeliver=True,
        )

        call_command("trigger_redelivery", "--batchsize=1", "--delay=0")

        releases_list_dict_1 = [
            {
                "delivery": {
                    "type": "insert",
                    "stores": [],
                    "countries": [],
                    "is_redelivery_for_bdr": bdr.pk,
                },
                "release": {},
            }
        ]
        releases_list_dict_2 = [
            {
                "delivery": {
                    "type": "insert",
                    "stores": [],
                    "countries": [],
                    "is_redelivery_for_bdr": bdr_2.pk,
                },
                "release": {},
            }
        ]

        assert mock_trigger_batch.call_count == 2

        assert mock.call(releases_list_dict_1, None) in mock_trigger_batch.mock_calls
        assert mock.call(releases_list_dict_2, None) in mock_trigger_batch.mock_calls

        mock_sleep.assert_called_with(0)
        assert mock_sleep.call_count == 2

        bdr.refresh_from_db()
        bdr_2.refresh_from_db()

        assert bdr.redeliver is False
        assert bdr.status == BatchDeliveryRelease.STATUS_REDELIVERED
        assert bdr_2.redeliver is False
        assert bdr_2.status == BatchDeliveryRelease.STATUS_REDELIVERED

    @mock.patch(SLEEP_PATH)
    @mock.patch("amuse.services.delivery.helpers.release_json")
    @mock.patch(TRIGGER_BATCH_DELIVERY_PATH)
    def test_fuga_redelivery_takedown(
        self, mock_trigger_batch, mock_release_json, mock_sleep
    ):
        for i in range(3):
            ReleaseFactory()

        mock_trigger_batch.return_value = 999
        mock_release_json.return_value = {}

        release = Release.objects.first()
        release.stores.add(
            self.store_shazam, self.store_napster, self.store_tiktok, self.store_spotify
        )

        release_2 = Release.objects.last()
        release_2.stores.add(self.store_napster, self.store_tiktok, self.store_spotify)

        delivery = BatchDeliveryFactory(channel=FUGA)
        bdr = BatchDeliveryReleaseFactory(
            release=release,
            delivery=delivery,
            type=BatchDeliveryRelease.DELIVERY_TYPE_TAKEDOWN,
            status=BatchDeliveryRelease.STATUS_CREATED,
            redeliver=True,
        )
        delivery_2 = BatchDeliveryFactory(channel=FUGA)
        bdr_2 = BatchDeliveryReleaseFactory(
            release=release_2,
            delivery=delivery,
            type=BatchDeliveryRelease.DELIVERY_TYPE_TAKEDOWN,
            status=BatchDeliveryRelease.STATUS_CREATED,
            redeliver=True,
        )
        ReleaseStoreDeliveryStatusFactory(
            release=release,
            fuga_store=self.fuga_napster,
            status=ReleaseStoreDeliveryStatus.STATUS_DELIVERED,
        )
        ReleaseStoreDeliveryStatusFactory(
            release=release_2,
            fuga_store=self.fuga_napster,
            status=ReleaseStoreDeliveryStatus.STATUS_DELIVERED,
        )

        call_command("trigger_redelivery", "--batchsize=1", "--delay=0")

        releases_list_dict_1 = [
            {
                "delivery": {
                    "type": "takedown",
                    "stores": ["fuga_napster"],
                    "countries": list(
                        release.included_countries.values_list("code", flat=True)
                    ),
                    "is_redelivery_for_bdr": bdr.pk,
                },
                "release": {},
            }
        ]
        releases_list_dict_2 = [
            {
                "delivery": {
                    "type": "takedown",
                    "stores": ["fuga_napster"],
                    "countries": list(
                        release_2.included_countries.values_list("code", flat=True)
                    ),
                    "is_redelivery_for_bdr": bdr_2.pk,
                },
                "release": {},
            }
        ]

        assert mock_trigger_batch.call_count == 2

        assert mock.call(releases_list_dict_1, None) in mock_trigger_batch.mock_calls
        assert mock.call(releases_list_dict_2, None) in mock_trigger_batch.mock_calls

        mock_sleep.assert_called_with(0)
        assert mock_sleep.call_count == 2

        bdr.refresh_from_db()
        bdr_2.refresh_from_db()

        assert bdr.redeliver is False
        assert bdr.status == BatchDeliveryRelease.STATUS_REDELIVERED
        assert bdr_2.redeliver is False
        assert bdr_2.status == BatchDeliveryRelease.STATUS_REDELIVERED

    @mock.patch(SLEEP_PATH)
    @mock.patch("amuse.services.delivery.helpers.release_json")
    @mock.patch(TRIGGER_BATCH_DELIVERY_PATH)
    def test_fuga_redelivery_update(
        self, mock_trigger_batch, mock_release_json, mock_sleep
    ):
        for i in range(3):
            ReleaseFactory()

        mock_trigger_batch.return_value = 999
        mock_release_json.return_value = {}

        release = Release.objects.first()
        release.stores.add(
            self.store_shazam, self.store_napster, self.store_tiktok, self.store_spotify
        )

        release_2 = Release.objects.last()
        release_2.stores.add(self.store_napster, self.store_tiktok, self.store_spotify)

        delivery = BatchDeliveryFactory(channel=FUGA)
        bdr = BatchDeliveryReleaseFactory(
            release=release,
            delivery=delivery,
            type=BatchDeliveryRelease.DELIVERY_TYPE_UPDATE,
            status=BatchDeliveryRelease.STATUS_CREATED,
            redeliver=True,
        )
        delivery_2 = BatchDeliveryFactory(channel=FUGA)
        bdr_2 = BatchDeliveryReleaseFactory(
            release=release_2,
            delivery=delivery,
            type=BatchDeliveryRelease.DELIVERY_TYPE_UPDATE,
            status=BatchDeliveryRelease.STATUS_CREATED,
            redeliver=True,
        )
        ReleaseStoreDeliveryStatusFactory(
            release=release,
            fuga_store=self.fuga_napster,
            status=ReleaseStoreDeliveryStatus.STATUS_DELIVERED,
        )
        ReleaseStoreDeliveryStatusFactory(
            release=release_2,
            fuga_store=self.fuga_napster,
            status=ReleaseStoreDeliveryStatus.STATUS_DELIVERED,
        )

        call_command("trigger_redelivery", "--batchsize=1", "--delay=0")

        releases_list_dict_1 = [
            {
                "delivery": {
                    "type": "update",
                    "stores": ["fuga_napster"],
                    "countries": list(
                        release.included_countries.values_list("code", flat=True)
                    ),
                    "is_redelivery_for_bdr": bdr.pk,
                },
                "release": {},
            }
        ]
        releases_list_dict_2 = [
            {
                "delivery": {
                    "type": "update",
                    "stores": ["fuga_napster"],
                    "countries": list(
                        release_2.included_countries.values_list("code", flat=True)
                    ),
                    "is_redelivery_for_bdr": bdr_2.pk,
                },
                "release": {},
            }
        ]

        assert mock_trigger_batch.call_count == 2
        assert mock.call(releases_list_dict_1, None) in mock_trigger_batch.mock_calls
        assert mock.call(releases_list_dict_2, None) in mock_trigger_batch.mock_calls

        mock_sleep.assert_called_with(0)
        assert mock_sleep.call_count == 2

        bdr.refresh_from_db()
        bdr_2.refresh_from_db()

        assert bdr.redeliver is False
        assert bdr.status == BatchDeliveryRelease.STATUS_REDELIVERED
        assert bdr_2.redeliver is False
        assert bdr_2.status == BatchDeliveryRelease.STATUS_REDELIVERED

    @mock.patch(
        "amuse.services.delivery.management.commands.trigger_automatic_delivery.deliver_batches"
    )
    def test_approved_auto_delivery(self, mock_deliver_batches):
        for i in range(2):
            ReleaseFactory()

        release = Release.objects.first()
        release.status = Release.STATUS_APPROVED
        release.stores.add(self.store_soundcloud)

        user = UserFactory()

        call_command(
            "trigger_automatic_delivery",
            "--status=approved",
            "--delay=0",
            "--fuga_delay=0",
            f"--user_id={user.id}",
        )

        mock_deliver_batches.assert_called_once_with(
            batchsize=10,
            delay=0.0,
            delivery_type='insert',
            dryrun=False,
            override_stores=False,
            releases=[release],
            stores=['soundcloud'],
            user=user,
        )

    @mock.patch(
        "amuse.services.delivery.management.commands.trigger_automatic_delivery.deliver_batches"
    )
    def test_approved_auto_delivery_only_allows_defined_error_flags(
        self, mock_deliver_batches
    ):
        for i in range(3):
            ReleaseFactory(status=Release.STATUS_APPROVED)

        releases = Release.objects.all()

        for release in releases:
            release.stores.add(self.store_soundcloud)

        release_1 = releases[0]
        release_2 = releases[1]
        release_3 = releases[2]

        song_1 = SongFactory(release=release_1)
        song_2 = SongFactory(release=release_2)
        song_3 = SongFactory(release=release_3)
        song_4 = SongFactory(release=release_3)

        assert release_1.error_flags.mask == 0 == release_2.error_flags.mask
        assert song_1.error_flags.mask == 0 == song_2.error_flags.mask

        # 19 is Release.error_flags.metadata_symbols-emoji-info that is allowed
        release_1.error_flags.set_bit(19, True)
        release_1.save()

        assert release_1.error_flags.mask == 524288

        # 4 is Song.error_flags.explicit_lyrics that is allowed
        song_1.error_flags.set_bit(4, True)
        song_1.save()

        assert song_1.error_flags.mask == 16

        # These are not allowed flags
        release_2.error_flags.set_bit(1, True)
        release_2.error_flags.set_bit(2, True)
        release_2.error_flags.set_bit(3, True)
        release_2.save()

        # This flag is not allowed
        song_4.error_flags.set_bit(1, True)
        song_4.save()

        # 4 is Song.error_flags.explicit_lyrics that is allowed
        song_3.error_flags.set_bit(4, True)
        song_3.save()

        user = UserFactory()

        call_command(
            "trigger_automatic_delivery",
            "--status=approved",
            "--delay=0",
            "--fuga_delay=0",
            f"--user_id={user.id}",
        )

        mock_deliver_batches.assert_called_once_with(
            batchsize=10,
            delay=0.0,
            delivery_type='insert',
            dryrun=False,
            override_stores=False,
            releases=[release_1],
            stores=['soundcloud'],
            user=user,
        )

    @mock.patch(
        "amuse.services.delivery.management.commands.trigger_automatic_delivery.deliver_batches"
    )
    def test_approved_auto_delivery_only_delivers_for_specified_agent_ids(
        self, mock_deliver_batches
    ):
        for i in range(2):
            ReleaseFactory(status=Release.STATUS_APPROVED)

        release = Release.objects.first()
        release.stores.add(self.store_soundcloud)

        user = UserFactory()

        SupportReleaseFactory(assignee=user, release=release)

        call_command(
            "trigger_automatic_delivery",
            "--status=approved",
            "--delay=0",
            "--fuga_delay=0",
            f"--user_id={user.id}",
            f"--agent_ids={user.id}",
        )

        mock_deliver_batches.assert_called_once_with(
            batchsize=10,
            delay=0.0,
            delivery_type='insert',
            dryrun=False,
            override_stores=False,
            releases=[release],
            stores=['soundcloud'],
            user=user,
        )

    @mock.patch(
        "amuse.services.delivery.management.commands.trigger_automatic_delivery.deliver_batches"
    )
    def test_approved_auto_delivery_picks_oldest_updated_release(
        self, mock_deliver_batches
    ):
        with freeze_time("2022-03-30"):
            release_1 = ReleaseFactory(status=Release.STATUS_APPROVED)
            release_1.stores.add(self.store_soundcloud)
            release_1.updated = datetime.now()
            release_1.save()

        with freeze_time("2022-03-20"):
            release_2 = ReleaseFactory(status=Release.STATUS_APPROVED)
            release_2.stores.add(self.store_soundcloud)
            release_2.updated = datetime.now()
            release_2.save()

        with freeze_time("2022-03-15"):
            release_3 = ReleaseFactory(status=Release.STATUS_APPROVED)
            release_3.stores.add(self.store_soundcloud)
            release_3.updated = datetime.now()
            release_3.save()

        user = UserFactory()

        with freeze_time("2022-03-30"):
            call_command(
                "trigger_automatic_delivery",
                "--status=approved",
                "--limit=1",
                "--days=30",
                "--delay=0",
                "--fuga_delay=0",
                f"--user_id={user.id}",
            )

        mock_deliver_batches.assert_called_once_with(
            batchsize=10,
            delay=0.0,
            delivery_type='insert',
            dryrun=False,
            override_stores=False,
            releases=[release_3],
            stores=['soundcloud'],
            user=user,
        )

    @mock.patch("amuse.services.delivery.encoder._calculate_django_file_checksum")
    @mock.patch("amuse.services.delivery.helpers.trigger_batch_delivery")
    def test_approved_auto_delivery_amazon_twitch_bundle_only_triggers_twitch(
        self, mock_trigger, mock_calculate
    ):
        for i in range(2):
            ReleaseFactory()

        release = Release.objects.first()
        artist_1 = release.user.create_artist_v2(name="Main Primary Artist")
        ReleaseArtistRoleFactory(
            release=release,
            artist=artist_1,
            role=ReleaseArtistRole.ROLE_PRIMARY_ARTIST,
            main_primary_artist=True,
        )
        song = SongFactory(release=release)
        SongFileFactory(song=song, type=SongFile.TYPE_FLAC)
        SongArtistRoleFactory(
            song=song,
            artist=artist_1,
            role=SongArtistRole.ROLE_PRIMARY_ARTIST,
            artist_sequence=1,
        )
        cover_art = CoverArtFactory(
            release=release, user=release.user, file__filename='cover.jpg'
        )

        cover_art.checksum = _calculate_django_file_checksum(cover_art.file)
        cover_art.save()
        release.status = Release.STATUS_APPROVED
        release.stores.add(self.store_amazon, self.store_twitch)
        release.save()
        mock_calculate.return_value = release.cover_art.checksum

        user = UserFactory()

        call_command(
            "trigger_automatic_delivery",
            "--status=approved",
            "--delay=0",
            "--fuga_delay=0",
            f"--user_id={user.id}",
        )

        assert mock_trigger.call_count == 1
        assert mock_trigger.call_args[0][0][0]["delivery"]["stores"] == ["twitch"]

    @mock.patch("amuse.tasks.zendesk_create_or_update_user")
    def test_approved_auto_delivery_no_main_primary_artist(self, _):
        user = UserFactory()
        release = ReleaseFactory(user=user, status=Release.STATUS_PENDING)
        release.status = Release.STATUS_APPROVED
        release.stores.add(self.store_soundcloud)
        release.save()
        artist_1 = release.user.create_artist_v2(name="Non Primary Artist")
        ReleaseArtistRoleFactory(
            release=release,
            artist=artist_1,
            role=ReleaseArtistRole.ROLE_FEATURED_ARTIST,
            main_primary_artist=False,
        )

        with self.assertRaises(AttributeError) as context:
            call_command(
                "trigger_automatic_delivery",
                "--status=approved",
                "--delay=0",
                "--fuga_delay=0",
                f"--user_id={user.id}",
            )

    @mock.patch(
        "amuse.services.delivery.management.commands.trigger_automatic_delivery.logger.error"
    )
    def test_delivered_auto_delivery_requires_valid_status_type(self, mock_logger):
        call_command("trigger_automatic_delivery", "--status=amused")
        mock_logger.assert_called_once()

    @freeze_time("2020-09-10")
    @mock.patch(
        "amuse.services.delivery.management.commands.trigger_automatic_delivery.deliver_batches"
    )
    def test_approved_auto_delivery_limit_days(self, mock_deliver_batches):
        for i in range(4):
            ReleaseFactory(status=Release.STATUS_PENDING)

        releases = Release.objects.all()[:3]

        for r in releases:
            r.status = Release.STATUS_APPROVED
            r.stores.add(self.store_soundcloud)

        with freeze_time("2020-09-01"):
            releases[0].updated = datetime.now()
            releases[0].save()
            releases[0].refresh_from_db()

        with freeze_time("2020-09-09"):
            releases[1].updated = datetime.now()
            releases[1].save()
            releases[1].refresh_from_db()

        with freeze_time("2020-09-10"):
            releases[2].updated = datetime.now()
            releases[2].save()
            releases[2].refresh_from_db()

        user = UserFactory()

        call_command(
            "trigger_automatic_delivery",
            "--status=approved",
            "--delay=0",
            "--fuga_delay=0",
            f"--user_id={user.id}",
            "--days=2",
        )

        mock_deliver_batches.assert_called_once_with(
            batchsize=10,
            delay=0.0,
            delivery_type='insert',
            dryrun=False,
            override_stores=False,
            releases=[releases[1], releases[2]],
            stores=['soundcloud'],
            user=user,
        )

    @freeze_time("2020-09-10")
    @mock.patch(
        "amuse.services.delivery.management.commands.trigger_automatic_delivery.deliver_batches"
    )
    def test_approved_auto_delivery_no_limit_days(self, mock_deliver_batches):
        for i in range(4):
            ReleaseFactory(id=i, status=Release.STATUS_PENDING)

        releases = Release.objects.all()[:3]

        for r in releases:
            r.status = Release.STATUS_APPROVED
            r.stores.add(self.store_soundcloud)

        with freeze_time("2020-09-01"):
            releases[0].updated = datetime.now()
            releases[0].save()
            releases[0].refresh_from_db()

        with freeze_time("2020-09-09"):
            releases[1].updated = datetime.now()
            releases[1].save()
            releases[1].refresh_from_db()

        with freeze_time("2020-09-10"):
            releases[2].updated = datetime.now()
            releases[2].save()
            releases[2].refresh_from_db()

        user = UserFactory()

        call_command(
            "trigger_automatic_delivery",
            "--status=approved",
            "--delay=0",
            "--fuga_delay=0",
            f"--user_id={user.id}",
            "--days=0",
        )

        mock_deliver_batches.assert_called_once_with(
            batchsize=10,
            delay=0.0,
            delivery_type='insert',
            dryrun=False,
            override_stores=False,
            releases=[releases[0], releases[1], releases[2]],
            stores=['soundcloud'],
            user=user,
        )

    @mock.patch(
        "amuse.services.delivery.management.commands.trigger_automatic_delivery.deliver_batches"
    )
    def test_missing_deliveries_auto_delivery(self, mock_deliver_batches):
        for i in range(2):
            ReleaseFactory()

        release = Release.objects.first()
        release.status = Release.STATUS_DELIVERED
        release.save()
        release.stores.set(
            [
                self.store_napster,
                self.store_youtube_music,
                self.store_youtube_content_id,
                self.store_deezer,
                self.store_spotify,
            ]
        )

        ReleaseStoreDeliveryStatusFactory(
            release=release,
            fuga_store=self.fuga_napster,
            status=ReleaseStoreDeliveryStatus.STATUS_DELIVERED,
        )
        ReleaseStoreDeliveryStatusFactory(
            release=release,
            store=self.store_spotify,
            status=ReleaseStoreDeliveryStatus.STATUS_DELIVERED,
        )

        call_command(
            "trigger_automatic_delivery",
            "--status=delivered",
            "--delay=0",
            "--fuga_delay=0",
        )

        assert mock_deliver_batches.call_count == 3
        assert mock_deliver_batches.called_once_with(
            mock.call(
                releases=[release],
                delivery_type='insert',
                override_stores=False,
                stores=['youtube_music'],
                batchsize=10,
                delay=0.0,
                dryrun=False,
                user=None,
            )
        )
        assert mock_deliver_batches.called_once_with(
            mock.call(
                releases=[release],
                delivery_type='insert',
                override_stores=False,
                stores=['deezer'],
                batchsize=10,
                delay=0.0,
                dryrun=False,
                user=None,
            )
        )
        assert mock_deliver_batches.called_once_with(
            mock.call(
                releases=[release],
                delivery_type='insert',
                override_stores=False,
                stores=['youtube_content_id'],
                batchsize=10,
                delay=0.0,
                dryrun=False,
                user=None,
            )
        )

    @mock.patch(
        "amuse.services.delivery.management.commands.trigger_automatic_delivery.deliver_batches"
    )
    def test_missing_deliveries_selective_auto_delivery(self, mock_deliver_batches):
        for i in range(2):
            ReleaseFactory()

        release = Release.objects.first()
        release.status = Release.STATUS_DELIVERED
        release.save()
        release.stores.set(
            [
                self.store_napster,
                self.store_youtube_music,
                self.store_youtube_music,
                self.store_deezer,
                self.store_spotify,
            ]
        )

        delivery_1 = BatchDeliveryFactory(
            status=BatchDelivery.STATUS_SUCCEEDED, channel=FUGA
        )
        delivery_2 = BatchDeliveryFactory(
            status=BatchDelivery.STATUS_SUCCEEDED, channel=SPOTIFY
        )
        bdr_1 = BatchDeliveryReleaseFactory(
            status=BatchDeliveryRelease.STATUS_SUCCEEDED,
            type=BatchDeliveryRelease.DELIVERY_TYPE_INSERT,
            delivery=delivery_1,
            release_id=release.id,
        )
        bdr_2 = BatchDeliveryReleaseFactory(
            status=BatchDeliveryRelease.STATUS_SUCCEEDED,
            type=BatchDeliveryRelease.DELIVERY_TYPE_INSERT,
            delivery=delivery_2,
            release_id=release.id,
        )

        call_command(
            "trigger_automatic_delivery",
            "--status=delivered",
            "--stores=youtube_music",
            "--bdr_id_start=%s" % bdr_1.pk,
            "--bdr_id_end=%s" % bdr_2.pk,
            "--delay=0",
            "--fuga_delay=0",
        )

        assert mock_deliver_batches.call_args_list == [
            mock.call(
                batchsize=10,
                delay=0.0,
                delivery_type='insert',
                dryrun=False,
                override_stores=False,
                releases=[release],
                stores=['youtube_music'],
                user=None,
            )
        ]

    @mock.patch(
        "amuse.services.delivery.management.commands.trigger_automatic_delivery.deliver_batches"
    )
    def test_auto_delivery_skips_partially_taken_down_release(
        self, mock_deliver_batches
    ):
        # Partially taken down release that should be skipped
        release_1 = ReleaseFactory()

        # Release that should be processed
        release_2 = ReleaseFactory()

        # Release that should be skipped as status is wrong
        release_3 = ReleaseFactory()

        release_1.status = Release.STATUS_DELIVERED
        release_2.status = Release.STATUS_DELIVERED

        release_1.save()
        release_2.save()

        release_1.stores.set(
            [
                self.store_napster,
                self.store_youtube_music,
                self.store_youtube_music,
                self.store_deezer,
                self.store_spotify,
            ]
        )
        release_2.stores.set([self.store_napster, self.store_youtube_music])
        release_3.stores.set([self.store_spotify, self.store_napster])

        ReleaseStoreDeliveryStatusFactory(
            release=release_1,
            fuga_store=self.fuga_napster,
            status=ReleaseStoreDeliveryStatus.STATUS_DELIVERED,
        )
        ReleaseStoreDeliveryStatusFactory(
            release=release_2,
            fuga_store=self.fuga_napster,
            status=ReleaseStoreDeliveryStatus.STATUS_DELIVERED,
        )
        ReleaseStoreDeliveryStatusFactory(
            release=release_1,
            store=self.store_spotify,
            status=ReleaseStoreDeliveryStatus.STATUS_TAKEDOWN,
        )

        call_command(
            "trigger_automatic_delivery",
            "--status=delivered",
            "--stores=youtube_music",
            "--delay=0",
            "--fuga_delay=0",
        )

        assert mock_deliver_batches.call_args_list == [
            mock.call(
                batchsize=10,
                delay=0.0,
                delivery_type='insert',
                dryrun=False,
                override_stores=False,
                releases=[release_2],
                stores=['youtube_music'],
                user=None,
            )
        ]

    @mock.patch(
        "amuse.services.delivery.management.commands.trigger_redelivery.deliver_batches"
    )
    def test_partially_failed_redelivery_sets_correct_status(
        self, mock_delivery_batches
    ):
        for i in range(3):
            ReleaseFactory()

        mock_delivery_batches.side_effect = [True, ValueError]
        releases = Release.objects.all()

        for release in releases:
            batch = BatchFactory()
            delivery = BatchDeliveryFactory(channel=SOUNDCLOUD, batch=batch)
            BatchDeliveryReleaseFactory(
                release=release,
                delivery=delivery,
                status=BatchDeliveryRelease.STATUS_FAILED,
            )

        bdr = BatchDeliveryRelease.objects.all().order_by("id")
        bdr_ids = list(bdr.values_list("id", flat=True))

        bdr_1 = bdr[0]
        bdr_2 = bdr[1]

        bdr_1.delivery.channel = TIKTOK
        bdr_1.type = BatchDeliveryRelease.DELIVERY_TYPE_UPDATE
        bdr_1.redeliver = True
        bdr_1.delivery.save()
        bdr_1.save()

        bdr_2.delivery.channel = SOUNDCLOUD
        bdr_2.type = BatchDeliveryRelease.DELIVERY_TYPE_TAKEDOWN
        bdr_2.redeliver = True
        bdr_2.delivery.save()
        bdr_2.save()

        with self.assertRaises(ValueError):
            call_command("trigger_redelivery", "--batchsize=1", "--delay=0")

        assert mock_delivery_batches.call_count == 2

        bdr_1.refresh_from_db()
        bdr_2.refresh_from_db()

        assert bdr_1.redeliver is False and bdr_2.redeliver is True
        assert bdr_1.status == BatchDeliveryRelease.STATUS_REDELIVERED
        assert bdr_2.status == BatchDeliveryRelease.STATUS_FAILED
