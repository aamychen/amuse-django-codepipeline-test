import datetime
import logging

from django.core.management.base import BaseCommand

from amuse.tasks import save_song_file_checksum, save_cover_art_checksum
from releases.models import Release, SongFile


logger = logging.getLogger(__name__)


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument(
            "--limit",
            help="Limits the number of checksums that are fixed",
            type=int,
            default=10,
        )
        parser.add_argument(
            "--dryrun", action="store_true", help="Only print expected results"
        )

    def handle(self, *args, **kwargs):
        limit = kwargs.get("limit")
        dryrun = kwargs.get("dryrun")

        self.fix_song_file_checksums(limit, dryrun)

    def fix_song_file_checksums(self, limit, dryrun):
        query_kwargs = {"type": SongFile.TYPE_FLAC, "checksum__isnull": True}
        query_kwargs_exclude = {"song__release__status": Release.STATUS_DELETED}

        song_files_missing_checksum = (
            SongFile.objects.filter(**query_kwargs)
            .exclude(**query_kwargs_exclude)
            .order_by("-id")[:limit]
        )

        logger.info(
            f"Found {len(song_files_missing_checksum)} songfiles with missing checksums"
        )

        if dryrun:
            for song_file in song_files_missing_checksum:
                logger.info(f"save_song_file_checksum for {song_file.pk}")
        else:
            for song_file in song_files_missing_checksum:
                save_song_file_checksum.apply_async(args=[song_file.pk], countdown=5)
