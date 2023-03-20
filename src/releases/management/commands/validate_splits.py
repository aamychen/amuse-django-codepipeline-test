import logging
import json

from dateutil.parser import isoparse
from django.core.management.base import BaseCommand

from releases.models import Song
from releases.validators import validate_splits_for_songs


logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Validate royalty splits"

    def add_arguments(self, parser):
        parser.add_argument(
            "--start-date",
            type=isoparse,
            help="Release dates starting from this date. Example: 2019-01-01",
        )
        parser.add_argument(
            "--end-date",
            type=isoparse,
            help="Release dates up until this date. Example: 2019-12-31",
        )

    def handle(self, *args, **kwargs):
        start_date = kwargs.get("start_date", None)
        end_date = kwargs.get("end_date", None)

        if bool(start_date) is not bool(end_date):
            self.stdout.write(
                "Both start and end date must be specified or none of them"
            )
            return

        kwargs = {"royalty_splits__isnull": False}

        if start_date and end_date:
            kwargs["release__release_date__range"] = (start_date, end_date)

        song_ids = list(Song.objects.filter(**kwargs).values_list("id", flat=True))

        self.stdout.write("Validate splits for %s songs" % len(song_ids))

        result_dict = validate_splits_for_songs(song_ids)
        result_json = json.dumps(result_dict)

        logger.info("Validate splits %s" % result_json)
        self.stdout.write(result_json)
