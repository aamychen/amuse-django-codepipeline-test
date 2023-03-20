import datetime
from random import randint

from django.core.management.base import BaseCommand

from amuse.tasks import save_song_file_checksum, save_cover_art_checksum
from releases.models import Release

DATE_FORMAT = '%Y-%m-%d'


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument(
            '--startdate',
            action='store',
            help='Releases with release date on, or after, this date',
            default=datetime.datetime.today().strftime(DATE_FORMAT),
        )

        parser.add_argument(
            '--enddate',
            action='store',
            help='Releases with release date on, or before, this date',
        )

        parser.add_argument(
            '--limit',
            action='store',
            help='Limits the number of CoverArts that are fixed',
            type=int,
            default=0,
        )

        parser.add_argument(
            '--noop',
            action='store_true',
            help='Only print files that would be migrated',
        )

    def handle(self, *args, **options):
        start_date = datetime.datetime.strptime(options['startdate'], DATE_FORMAT)

        releases = Release.objects.filter(release_date__gte=start_date)

        if options['enddate']:
            end_date = datetime.datetime.strptime(options['enddate'], DATE_FORMAT)
            releases = releases.filter(release_date__lte=end_date)

        releases = releases.all()

        if options['limit']:
            releases = releases[: options['limit']]

        for release in releases:
            self.stdout.write(f'Release: {release.id}')
            try:
                self.cover_art_checksum(release.cover_art, noop=options['noop'])
            except Exception as e:
                self.stderr(f'Could not calculate CoverArt checksum: {e}')

            for song in release.songs.all():
                self.song_file_checksums(song.files.all(), noop=options['noop'])

    def song_file_checksums(self, song_files, noop):
        for song_file in song_files:
            if song_file.checksum:
                self.stdout.write(f'SongFile {song_file.id} already has a checksum')
                continue

            if noop:
                self.stdout.write(
                    f'NOOP: Calculate checksum for SongFile {song_file.id}'
                )
            else:
                self.stdout.write(f'SongFile checksum task: ID {song_file.id}')
                save_song_file_checksum.apply_async(
                    args=[song_file.id], countdown=randint(1, 90)
                )

    def cover_art_checksum(self, cover_art, noop):
        if cover_art.checksum:
            self.stdout.write(f'CoverArt {cover_art.id} already has a checksum')
            return

        if noop:
            self.stdout.write(f'NOOP: Calculate checksum for CoverArt {cover_art.id}')
        else:
            self.stdout.write(f'CoverArt checksum task: ID {cover_art.id}')
            save_cover_art_checksum.apply_async(
                args=[cover_art.id], countdown=randint(1, 90)
            )
