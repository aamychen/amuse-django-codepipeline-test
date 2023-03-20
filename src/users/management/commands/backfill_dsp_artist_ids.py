import argparse
import csv
import re
from uuid import uuid4

from django.core.management.base import BaseCommand
from django.db.models import Q

from amuse.vendor.aws.s3 import download_file
from users.models import ArtistV2


class Command(BaseCommand):
    help = "Backfill artists with DSP artist ids from CSV file."

    def add_arguments(self, parser):
        parser.add_argument(
            "--backfill-field", type=str, help="Supported fields: apple_id, spotify_id"
        )
        parser.add_argument(
            "--file",
            type=argparse.FileType('r'),
            help="CSV Format: amuse_artist_id | dsp_artist_id",
        )
        parser.add_argument("--s3-file", help="S3 file path")
        parser.add_argument(
            "--start", type=int, help="Specify from what row in CSV to process"
        )
        parser.add_argument(
            "--end", type=int, help="Specify to what row in CSV to process"
        )
        parser.add_argument(
            "--batchsize", type=int, help="Specify SQL batch size. Defaults to 1000"
        )
        parser.add_argument(
            "--dryrun",
            action="store_true",
            default=False,
            help="Only print results and doesn't write to database",
        )

    def handle(self, *args, **kwargs):
        backfill_field = kwargs.get("backfill_field")
        local_file = kwargs.get("file")
        s3_file = kwargs.get("s3_file")
        start = kwargs.get("start")
        end = kwargs.get("end")
        batchsize = kwargs.get("batchsize")
        dryrun = kwargs.get("dryrun")

        assert backfill_field in ("apple_id", "spotify_id")

        if (local_file and s3_file) or (not local_file and not s3_file):
            self.stdout.write("Need to specify a local file OR a s3 file")
            return

        data = self.get_data(local_file=local_file, s3_file=s3_file)

        if not batchsize:
            batchsize = 1_000

        if dryrun:
            self.stdout.write("Running in Dry Run mode")

        original_count = len(data)

        if start and end:
            if start >= original_count or end > original_count:
                self.stdout.write(
                    "--start and --end must be smaller than the total number of rows."
                )
                return

            self.stdout.write("Limit processing to rows %s-%s" % (start, end))
            data = data[start:end]

        self.stdout.write("Start processing %s rows" % len(data))

        try:
            self.validate_dsp_ids(
                backfill_field=backfill_field, ids=[row["dsp_id"] for row in data]
            )
        except ValueError:
            return

        self.update_artists(
            data=data, backfill_field=backfill_field, batchsize=batchsize, dryrun=dryrun
        )

    def get_data(self, local_file, s3_file):
        if local_file:
            data = list(csv.DictReader(local_file, delimiter=","))
        elif s3_file:
            file_name = "/tmp/%s" % str(uuid4())
            download_file("amuse-artist-id-backfill", s3_file, file_name)
            with open(file_name) as f:
                data = list(csv.DictReader(f, delimiter=","))

        return data

    def update_artists(self, data, backfill_field, batchsize, dryrun):
        # Have to do this as the model allows both null and empty strings..
        artists = ArtistV2.objects.filter(
            Q((backfill_field, None)) | Q((backfill_field, "")),
            pk__in=[row["artist_id"] for row in data],
        )

        self.stdout.write("Retrieved %s artists from the database" % len(artists))

        artist_dict = {int(row["artist_id"]): row["dsp_id"] for row in data}
        artist_diff = len(data) - artists.count()

        if artist_diff > 0:
            self.stdout.write(
                "%s artists were not retrieved from the db as they already have dsp ids"
                % artist_diff
            )

        for idx, artist in enumerate(artists, 1):
            if not dryrun:
                setattr(artist, backfill_field, artist_dict[artist.pk])

            self.stdout.write(
                "%s. UPDATED: amuse_artist_id: %s, %s: %s"
                % (idx, artist.pk, backfill_field, artist_dict[artist.pk])
            )

        if not dryrun:
            ArtistV2.objects.bulk_update(
                list(artists), [backfill_field], batch_size=batchsize
            )

    def validate_dsp_ids(self, backfill_field, ids):
        apple_pattern = re.compile("^[0-9]+$")
        spotify_pattern = re.compile("(?=.*[0-9])(?=.*[a-zA-Z])")

        for item in ids:
            if backfill_field == "apple_id":
                pattern = apple_pattern
            elif backfill_field == "spotify_id":
                pattern = spotify_pattern

            if pattern.match(item) is None:
                self.stdout.write(
                    "%s is not a valid format for %s" % (item, backfill_field)
                )
                raise ValueError()
