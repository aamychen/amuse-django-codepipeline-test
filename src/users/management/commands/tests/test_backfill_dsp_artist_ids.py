from collections import OrderedDict
from io import StringIO
from unittest import mock

from django.core.management import call_command
from django.test import TestCase

from users.management.commands.backfill_dsp_artist_ids import Command
from users.tests.factories import Artistv2Factory


class TestBackfillDSPArtistIds(TestCase):
    @mock.patch("amuse.tasks.zendesk_create_or_update_user")
    def setUp(self, mock_zendesk):
        self.apple_id_1 = "1192422451"
        self.apple_id_2 = "1324728311"
        self.apple_id_3 = "1456240785"
        self.spotify_id_1 = "4WNMaiVLHsLvWB97uZVxFL"
        self.spotify_id_2 = "3Aw8iOdSZoBwBh42CNdSqg"
        self.spotify_id_3 = "7s7YoqFFpyVL0V481Xrdo6"
        self.apple_id_existing = "1234567890"
        self.spotify_id_existing = "394LHcas8VEquIQqX2AHTr"

        self.artist_1 = Artistv2Factory(apple_id=None, spotify_id=None)
        self.artist_2 = Artistv2Factory(apple_id="", spotify_id="")
        self.artist_3 = Artistv2Factory(
            apple_id=self.apple_id_existing, spotify_id=self.spotify_id_existing
        )

    def test_backfill(self):
        with mock.patch("builtins.open") as mock_open:
            mock_open.return_value = StringIO(
                f"artist_id,dsp_id\n{self.artist_1.pk},{self.apple_id_1}\n{self.artist_2.pk},{self.apple_id_2}\n{self.artist_3.pk},{self.apple_id_3}\n"
            )
            call_command(
                "backfill_dsp_artist_ids",
                "--backfill-field=apple_id",
                "--file=fake.csv",
            )

        self.artist_1.refresh_from_db()
        self.artist_2.refresh_from_db()
        self.artist_3.refresh_from_db()

        assert self.artist_1.apple_id == self.apple_id_1
        assert self.artist_1.spotify_id is None
        assert self.artist_2.apple_id == self.apple_id_2
        assert self.artist_2.spotify_id == ""
        assert self.artist_3.apple_id == self.apple_id_existing
        assert self.artist_3.spotify_id == self.spotify_id_existing

    def test_backfill_slicing(self):
        with mock.patch("builtins.open") as mock_open:
            mock_open.return_value = StringIO(
                f"artist_id,dsp_id\n{self.artist_1.pk},{self.apple_id_1}\n{self.artist_2.pk},{self.apple_id_2}\n{self.artist_3.pk},{self.apple_id_3}\n"
            )
            call_command(
                "backfill_dsp_artist_ids",
                "--backfill-field=apple_id",
                "--file=fake.csv",
                "--start=1",
                "--end=2",
            )

        self.artist_1.refresh_from_db()
        self.artist_2.refresh_from_db()
        self.artist_3.refresh_from_db()

        assert self.artist_1.apple_id is None
        assert self.artist_1.spotify_id is None
        assert self.artist_2.apple_id == self.apple_id_2
        assert self.artist_2.spotify_id == ""
        assert self.artist_3.apple_id == self.apple_id_existing
        assert self.artist_3.spotify_id == self.spotify_id_existing

    def test_backfill_spotify_validation_failed(self):
        with mock.patch("builtins.open") as mock_open:
            mock_open.return_value = StringIO(
                f"artist_id,dsp_id\n{self.artist_1.pk},{self.apple_id_1}\n{self.artist_2.pk},{self.apple_id_2}\n{self.artist_3.pk},{self.apple_id_3}\n"
            )
            call_command(
                "backfill_dsp_artist_ids",
                "--backfill-field=spotify_id",
                "--file=fake.csv",
            )

        self.artist_1.refresh_from_db()
        self.artist_2.refresh_from_db()
        self.artist_3.refresh_from_db()

        assert self.artist_1.apple_id is None
        assert self.artist_1.spotify_id is None
        assert self.artist_2.apple_id == ""
        assert self.artist_2.spotify_id == ""
        assert self.artist_3.apple_id == self.apple_id_existing
        assert self.artist_3.spotify_id == self.spotify_id_existing

    def test_backfill_apple_validation_failed(self):
        with mock.patch("builtins.open") as mock_open:
            mock_open.return_value = StringIO(
                f"artist_id,dsp_id\n{self.artist_1.pk},{self.spotify_id_1}\n{self.artist_2.pk},{self.spotify_id_2}\n{self.artist_3.pk},{self.spotify_id_3}\n"
            )
            call_command(
                "backfill_dsp_artist_ids",
                "--backfill-field=apple_id",
                "--file=fake.csv",
            )

        self.artist_1.refresh_from_db()
        self.artist_2.refresh_from_db()
        self.artist_3.refresh_from_db()

        assert self.artist_1.apple_id is None
        assert self.artist_1.spotify_id is None
        assert self.artist_2.apple_id == ""
        assert self.artist_2.spotify_id == ""
        assert self.artist_3.apple_id == self.apple_id_existing
        assert self.artist_3.spotify_id == self.spotify_id_existing

    @mock.patch("users.management.commands.backfill_dsp_artist_ids.download_file")
    def test_backfill_s3_file(self, mock_download):
        with mock.patch("builtins.open") as mock_open:
            mock_open.return_value = StringIO(
                f"artist_id,dsp_id\n{self.artist_1.pk},{self.apple_id_1}\n{self.artist_2.pk},{self.apple_id_2}\n{self.artist_3.pk},{self.apple_id_3}\n"
            )
            call_command(
                "backfill_dsp_artist_ids",
                "--backfill-field=apple_id",
                "--s3-file=fake.csv",
            )

        self.artist_1.refresh_from_db()
        self.artist_2.refresh_from_db()
        self.artist_3.refresh_from_db()

        assert self.artist_1.apple_id == self.apple_id_1
        assert self.artist_1.spotify_id is None
        assert self.artist_2.apple_id == self.apple_id_2
        assert self.artist_2.spotify_id == ""
        assert self.artist_3.apple_id == self.apple_id_existing
        assert self.artist_3.spotify_id == self.spotify_id_existing

    def test_backfill_local_and_s3_file_exits(self):
        with mock.patch("builtins.open") as mock_open:
            mock_open.return_value = StringIO(
                f"artist_id,dsp_id\n{self.artist_1.pk},{self.apple_id_1}\n{self.artist_2.pk},{self.apple_id_2}\n{self.artist_3.pk},{self.apple_id_3}\n"
            )
            call_command(
                "backfill_dsp_artist_ids",
                "--backfill-field=apple_id",
                "--file=fake.csv",
                "--s3-file=fake.csv",
            )

        self.artist_1.refresh_from_db()
        self.artist_2.refresh_from_db()
        self.artist_3.refresh_from_db()

        assert self.artist_1.apple_id is None
        assert self.artist_1.spotify_id is None
        assert self.artist_2.apple_id == ""
        assert self.artist_2.spotify_id == ""
        assert self.artist_3.apple_id == self.apple_id_existing
        assert self.artist_3.spotify_id == self.spotify_id_existing

    def test_backfill_no_file_specified_exits(self):
        with mock.patch("builtins.open") as mock_open:
            mock_open.return_value = StringIO(
                f"artist_id,dsp_id\n{self.artist_1.pk},{self.apple_id_1}\n{self.artist_2.pk},{self.apple_id_2}\n{self.artist_3.pk},{self.apple_id_3}\n"
            )
            call_command("backfill_dsp_artist_ids", "--backfill-field=apple_id")

        self.artist_1.refresh_from_db()
        self.artist_2.refresh_from_db()
        self.artist_3.refresh_from_db()

        assert self.artist_1.apple_id is None
        assert self.artist_1.spotify_id is None
        assert self.artist_2.apple_id == ""
        assert self.artist_2.spotify_id == ""
        assert self.artist_3.apple_id == self.apple_id_existing
        assert self.artist_3.spotify_id == self.spotify_id_existing

    @mock.patch("sys.stdout.write")
    def test_dryrun(self, mock_write):
        with mock.patch("builtins.open") as mock_open:
            mock_open.return_value = StringIO(
                f"artist_id,dsp_id\n{self.artist_1.pk},{self.apple_id_1}\n{self.artist_2.pk},{self.apple_id_2}\n{self.artist_3.pk},{self.apple_id_3}\n"
            )
            call_command(
                "backfill_dsp_artist_ids",
                "--backfill-field=apple_id",
                "--file=fake.csv",
                "--dryrun",
            )

        assert mock_write.call_args_list[0] == mock.call("Running in Dry Run mode\n")

    @mock.patch.object(Command, "update_artists")
    def test_batchsize_pass_in_value(self, mock_update):
        with mock.patch("builtins.open") as mock_open:
            mock_open.return_value = StringIO(
                f"artist_id,dsp_id\n{self.artist_1.pk},{self.apple_id_1}\n{self.artist_2.pk},{self.apple_id_2}\n{self.artist_3.pk},{self.apple_id_3}\n"
            )
            call_command(
                "backfill_dsp_artist_ids",
                "--backfill-field=apple_id",
                "--file=fake.csv",
                "--batchsize=10",
            )

        expected_calls = [
            OrderedDict(
                [('artist_id', str(self.artist_1.pk)), ('dsp_id', self.apple_id_1)]
            ),
            OrderedDict(
                [('artist_id', str(self.artist_2.pk)), ('dsp_id', self.apple_id_2)]
            ),
            OrderedDict(
                [('artist_id', str(self.artist_3.pk)), ('dsp_id', self.apple_id_3)]
            ),
        ]

        mock_update.assert_called_once_with(
            backfill_field="apple_id", batchsize=10, data=expected_calls, dryrun=False
        )

    @mock.patch.object(Command, "update_artists")
    def test_batchsize_fallback(self, mock_update):
        with mock.patch("builtins.open") as mock_open:
            mock_open.return_value = StringIO(
                f"artist_id,dsp_id\n{self.artist_1.pk},{self.apple_id_1}\n{self.artist_2.pk},{self.apple_id_2}\n{self.artist_3.pk},{self.apple_id_3}\n"
            )
            call_command(
                "backfill_dsp_artist_ids",
                "--backfill-field=apple_id",
                "--file=fake.csv",
            )

        expected_calls = [
            OrderedDict(
                [('artist_id', str(self.artist_1.pk)), ('dsp_id', self.apple_id_1)]
            ),
            OrderedDict(
                [('artist_id', str(self.artist_2.pk)), ('dsp_id', self.apple_id_2)]
            ),
            OrderedDict(
                [('artist_id', str(self.artist_3.pk)), ('dsp_id', self.apple_id_3)]
            ),
        ]

        mock_update.assert_called_once_with(
            backfill_field="apple_id", batchsize=1000, data=expected_calls, dryrun=False
        )
