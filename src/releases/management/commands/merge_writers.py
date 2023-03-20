from django.core.management.base import BaseCommand
from datetime import timedelta
from django.utils import timezone
from releases.models import Release, SongArtistRole
from django.db.models import Q
from collections import OrderedDict
from amuse.utils import match_strings
from django.db import transaction, IntegrityError
import time
from dateutil.parser import isoparse

DEBUG_MODE = 'debug'
DB_MODE = 'db'

DEFAULT_DAYS = 2
MODE = DB_MODE

# progress
p = None


def progress():
    global p
    if not p:
        p = Statistics()

    return p


def info(*args):
    # LOG.info(*args)
    print(*args)
    pass


def error(*args):
    print("  ERROR", *args)
    pass


def prepare_data(user_id):
    song_writer_roles = list(
        SongArtistRole.objects.filter(
            song__release__user_id=user_id,
            role=SongArtistRole.ROLE_WRITER,
            artist__isnull=False,
        ).prefetch_related('artist')
    )

    writers = dict()
    for sar in song_writer_roles:
        writers.setdefault(sar.artist, list()).append(sar)

    unmergeables = find_unmergeable_artists(song_writer_roles)

    return writers, unmergeables


def match_artists(first, second):
    spotify_id = first.spotify_id

    if spotify_id and spotify_id == second.spotify_id:
        return True

    if match_strings(first.name, second.name):
        return True

    return False


def find_matching_writers(writers, unmergeables):
    matches = dict()
    processed = set()

    count = len(writers)
    for i in range(0, count):
        actual = writers[i]
        matches.setdefault(actual, list()).append(actual)

        if not actual.name.strip():
            # do not merge artists with empty name
            return

        if actual in processed:
            # already processed and matched with other writer
            continue

        for j in range(i + 1, count):
            writer = writers[j]

            if actual == writer:
                continue

            if writer in processed:
                # already processed and matched with other writer
                continue

            excluded_writers = unmergeables.get(actual.id)
            if excluded_writers and writer.id in excluded_writers:
                # there are >=2 writers on same song. DO NOT MERGE!
                continue

            if match_artists(actual, writer):
                matches.setdefault(actual, list()).append(writer)
                processed.add(writer)
                update_unmergeables(unmergeables, actual.id, writer.id)

    return matches


@transaction.atomic
def process_user(user_id):
    writer_roles, unmergeables = prepare_data(user_id)
    writers = list(writer_roles.keys())

    if not writers:
        return

    matching_writers = find_matching_writers(writers, unmergeables)

    if not matching_writers:
        return

    for artist, matches in matching_writers.items():
        if len(matches) < 2:
            continue

        matches.sort(key=lambda x: x.id)
        oldest = matches[0]

        for writer in matches[1:]:
            if oldest.id != writer.id:
                roles = writer_roles[writer]
                merge_writer(oldest, roles)


def find_unmergeable_artists(writer_roles):
    by_song = OrderedDict()
    for sar in writer_roles:
        key = sar.song_id
        if not by_song.get(key):
            by_song[key] = set()

        by_song[key].add(sar.artist_id)

    unmergeable = OrderedDict()
    for item in by_song.values():
        for artist_id in item:
            if not unmergeable.get(artist_id):
                unmergeable[artist_id] = set()

            unmergeable[artist_id].update(item)

    for key, value in unmergeable.items():
        value.remove(key)

    return unmergeable


def update_unmergeables(unmergeables, writer_id1, writer_id2):
    artist_unmergeables = unmergeables.get(writer_id2)
    if not artist_unmergeables:
        return

    for unmergeable_artist_id in artist_unmergeables:
        s = (
            unmergeables.get(unmergeable_artist_id)
            if unmergeables.get(unmergeable_artist_id)
            else set()
        )
        s.add(writer_id1)
        unmergeables[unmergeable_artist_id] = s

        w = unmergeables.get(writer_id1) if unmergeables.get(writer_id1) else set()
        w.add(unmergeable_artist_id)
        unmergeables[writer_id1] = w


def merge_writer(writer, song_artist_roles):
    global MODE
    for sar in song_artist_roles:
        try:
            if MODE == DB_MODE:
                sar.artist = writer
                sar.save()
            elif MODE == DEBUG_MODE:
                info(
                    f'... {sar.artist.id}::{sar.artist.name} -> {writer.id}::{writer.name}'
                )
            progress().merged()
        except IntegrityError as e:
            info(e)


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument(
            '--days',
            help='Limits merging writers for the releases that are younger than specified number of days',
            type=int,
        )

        parser.add_argument(
            '--mode',
            help='DEBUG writes results to the stdout. DB writes results to the DB.',
            type=str,
            default=DB_MODE,
        )

        parser.add_argument(
            '--start-date', type=isoparse, help='2020-06-22T14:41:07Z', default=None
        )
        parser.add_argument(
            '--end-date', type=isoparse, help='2020-06-22T14:41:07Z', default=None
        )

        parser.add_argument(
            '--release-ids',
            nargs='+',
            type=int,
            help='Single/multiple release_ids separated by space. Example: 1 2 3 4',
        )

    def handle(self, *args, **kwargs):
        start_date = kwargs.get('start_date', None)
        end_date = kwargs.get('end_date', None)
        days = kwargs.get('days', None)
        mode = kwargs.get('mode', DB_MODE)
        release_ids = kwargs.get('release_ids')

        global MODE
        MODE = mode

        if (start_date or end_date) and days:
            error(f'Use "days" argument without "start_date" and "end_date" arguments')
            return

        if not start_date and not end_date and not days and not release_ids:
            days = DEFAULT_DAYS

        if MODE not in [DB_MODE, DEBUG_MODE]:
            error(
                f'Invalid mode value {mode}. Allowed values are [{DEBUG_MODE}, {DB_MODE}]'
            )
            return

        info(f'Running in {mode} mode')
        info(':: query filters ::')
        info(':: status: STATUS_NOT_APPROVED')
        qs = Release.objects.filter(~Q(status=Release.STATUS_NOT_APPROVED))

        if days:
            time_threshold = timezone.now() - timedelta(days=days)
            info(':: days:', days, f'[since: {time_threshold}]')
            qs = qs.filter(created__gte=time_threshold)

        if start_date:
            info(':: start_date:', start_date)
            qs = qs.filter(created__gte=start_date)

        if end_date:
            info(':: end_date:', end_date)
            qs = qs.filter(created__lte=end_date)

        if release_ids and len(release_ids) > 0:
            info(':: release_ids:', release_ids)
            qs = qs.filter(id__in=release_ids)

        info("Running query:", qs.query)
        user_ids = list(qs.distinct().values_list('user_id', flat=True))
        info(f"Total users={len(user_ids)}")

        progress().start(len(user_ids))
        for user_id in user_ids:
            process_user(user_id)

            progress().update(1)
            progress().report()

        progress().report(force=True)
        info("Command completed")


class Progress:
    def __init__(self, interval_seconds=10, prefix=""):
        self.start_time = None
        self.interval_seconds = interval_seconds
        self.last_interval = 0
        self.elapsed_time = 0
        self.prefix = prefix

        self.count_total = None
        self.count_done = 0

    def _eta(self):
        processed = self.count_done
        total = self.count_total

        if processed == 0:
            # sanity: zero division
            processed = 1

        return (self.elapsed_time / processed) * (total - processed)

    @staticmethod
    def _format_time(v):
        return time.strftime('%H:%M:%S', time.gmtime(v))

    def _percentage(self):
        processed = self.count_done
        total = self.count_total

        return processed / total * 100.0 if processed > 0 else 0

    def format_message(self):
        eta = self._eta()
        percent = self._percentage()
        elapsed_time_formatted = self._format_time(self.elapsed_time)
        estimated_time_remaining_formatted = self._format_time(eta)

        messages = [
            f'processed: {self.count_done}/{self.count_total} ({percent:.2f})%',
            f'elapsed: {elapsed_time_formatted}',
            f'ETA: ~{estimated_time_remaining_formatted}',
        ]

        return f'{self.prefix}{" :: ".join(messages)}'

    def report(self, force=False):
        if self.start_time is None:
            return

        self.elapsed_time = time.time() - self.start_time
        current_interval = int(self.elapsed_time / self.interval_seconds)

        if current_interval > self.last_interval or force:
            self.last_interval = current_interval

            message = self.format_message()

            info(message)

    def start(self, total):
        self.count_total = total
        self.start_time = time.time()

    def update(self, value=1):
        self.count_done += value


class Statistics(Progress):
    def __init__(self):
        super().__init__()
        self.count_merged = 0

    def merged(self, value=1):
        self.count_merged += value

    def format_message(self):
        msg = super().format_message()

        messages = [f'{msg}', f'merged roles: {self.count_merged}']

        return f'{" :: ".join(messages)}'
