import logging
from collections import defaultdict
from datetime import date, datetime
from decimal import Decimal

from dateutil.parser import isoparse
from django.core.management.base import BaseCommand

from releases.models import RoyaltySplit, Release, Song


logger = logging.getLogger(__name__)


RELEASE_STATUS_LIST = [
    Release.STATUS_DELIVERED,
    Release.STATUS_RELEASED,
    Release.STATUS_TAKEDOWN,
]
BOTH_DATES_ERROR_MSG = 'Both start and end date must be specified or none of them'
END_DATE_ERROR_MSG = (
    'Cannot cancel splits for releases that are not released.'
    '--end-date must be a date that is today or an earlier date.'
)


class Command(BaseCommand):
    help = """
    Cancels pending splits for songs that are released today and have no active splits
    for today's date and allocates the unconfirmed royalties back to the owner.
    This is safe to re-run as script will delete cancelled splits.
    """

    def add_arguments(self, parser):
        parser.add_argument(
            '--start-date',
            type=isoparse,
            help='Release dates starting from this date. Example: 2019-01-01',
        )
        parser.add_argument(
            '--end-date',
            type=isoparse,
            help='Release dates up until this date. Example: 2019-12-31',
        )

    def handle(self, *args, **kwargs):
        """
        We will fetch all revision 1 splits that are pending/confirmed for songs with
        release date today. We will create new revision 1 active splits for the songs
        with pending splits re-allocated back to the owner. We will then delete all
        existing splits for the song. The songs should only have revision 1 splits
        but we will delete all splits in case some other parts of the code has not
        cleaned it up so it has multiple revisions of pending splits.

        We will also look for songs without any splits and create 100% owner splits
        for them. This should not happen normally but this will serve as a clean-up
        job that covers that scenario in case some other parts of the code fails to
        prevent that.
        """
        start_date = kwargs.get('start_date', None)
        end_date = kwargs.get('end_date', None)

        if bool(start_date) is not bool(end_date):
            self.stdout.write(BOTH_DATES_ERROR_MSG)
            return

        if end_date and end_date > datetime.now():
            self.stdout.write(END_DATE_ERROR_MSG)
            return

        splits = get_splits_grouped_by_song(start_date=start_date, end_date=end_date)

        logger.info("Found %s songs with splits that are released today" % len(splits))

        new_revision_list, cancel_revision_list = get_split_revision_updates(splits)

        RoyaltySplit.objects.filter(song_id__in=cancel_revision_list).delete()
        RoyaltySplit.objects.bulk_create(new_revision_list)

        logger.info(
            "Cancelled %s old splits and created %s new splits"
            % (len(cancel_revision_list), len(new_revision_list))
        )

        filter_kwargs = {
            "royalty_splits__isnull": True,
            "release__status__in": RELEASE_STATUS_LIST,
        }

        if start_date and end_date:
            filter_kwargs["release__release_date__range"] = (start_date, end_date)
        else:
            filter_kwargs["release__release_date"] = date.today()

        songs_without_splits = Song.objects.filter(**filter_kwargs)
        songs_without_splits_count = len(songs_without_splits)

        logger.info(
            "Found %s songs without splits that are released today"
            % songs_without_splits_count
        )

        if songs_without_splits.exists():
            splits_for_songs_without_splits = generate_splits(songs_without_splits)
            RoyaltySplit.objects.bulk_create(splits_for_songs_without_splits)

            logger.info(
                "Created %s splits for songs without splits that are released today"
                % songs_without_splits_count
            )


def generate_splits(songs_without_splits):
    """
    Creating new active 100% on owner for songs that are missing splits.
    """
    return [
        RoyaltySplit(
            song_id=song.id,
            user_id=song.release.main_primary_artist.owner.id,
            rate=Decimal("1.00"),
            revision=1,
            status=RoyaltySplit.STATUS_ACTIVE,
            start_date=None,
            end_date=None,
            is_owner=True,
        )
        for song in songs_without_splits
    ]


def get_splits_grouped_by_song(start_date=None, end_date=None):
    filter_kwargs = {
        "status__in": [RoyaltySplit.STATUS_PENDING, RoyaltySplit.STATUS_CONFIRMED],
        "revision": 1,
        "song__release__status__in": RELEASE_STATUS_LIST,
    }

    if start_date and end_date:
        filter_kwargs["song__release__release_date__range"] = (start_date, end_date)
    else:
        filter_kwargs["song__release__release_date"] = date.today()

    splits = list(
        RoyaltySplit.objects.filter(**filter_kwargs)
        .select_related('song', 'song__release')
        .values('id', 'user_id', 'song_id', 'rate', 'status', 'is_owner')
    )

    splits_grouped_by_song = defaultdict(list)

    for split in splits:
        splits_grouped_by_song[split['song_id']].append(split)

    pending_splits_grouped_by_song = {}

    for song_id, splits in splits_grouped_by_song.items():
        pending_splits_grouped_by_song.update({song_id: splits})

    return pending_splits_grouped_by_song


def get_split_revision_updates(splits_grouped_by_song):
    new_revision_list = []
    cancel_revision_list = []

    for song_id, splits in splits_grouped_by_song.items():
        owner_rate = Decimal('0.0')
        owner_id = None
        song = Song.objects.get(id=song_id)

        if song.has_locked_splits():
            continue

        for split in splits:
            cancel_revision_list.append(split['song_id'])
            user_id = split['user_id']
            status = split['status']

            if split["is_owner"]:
                is_owner = True
                owner_id = user_id
            else:
                is_owner = False

            if is_owner or status == RoyaltySplit.STATUS_PENDING:
                owner_rate += split['rate']
            else:
                new_revision_list.append(
                    RoyaltySplit(
                        song_id=song_id,
                        user_id=user_id,
                        rate=split['rate'],
                        revision=1,
                        status=RoyaltySplit.STATUS_ACTIVE,
                        start_date=None,
                        end_date=None,
                    )
                )

        if owner_rate > 0:
            if owner_id is None:
                release = song.release
                owner_id = release.main_primary_artist.owner.id

            new_revision_list.append(
                RoyaltySplit(
                    song_id=song_id,
                    user_id=owner_id,
                    rate=owner_rate,
                    revision=1,
                    status=RoyaltySplit.STATUS_ACTIVE,
                    start_date=None,
                    end_date=None,
                    is_owner=True,
                )
            )

    return new_revision_list, cancel_revision_list
