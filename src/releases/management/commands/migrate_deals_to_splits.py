from datetime import date
from decimal import Decimal

from dateutil.parser import isoparse
from django.core.management.base import BaseCommand

from amuse.utils import chunks
from releases.models import RoyaltySplit, Song


class Command(BaseCommand):
    help = 'Creates 100% royalty splits for all users who are the owner of a song'

    def add_arguments(self, parser):
        parser.add_argument('--start-date', type=isoparse, help='2019-01-01')
        parser.add_argument('--end-date', type=isoparse, help='2019-12-31')
        parser.add_argument(
            '--batchsize', type=int, help='bulk_create batch_size', default=10000
        )

    def handle(self, *args, **kwargs):
        start_date = kwargs.get('start_date', None)
        end_date = kwargs.get('end_date', None)
        batch_size = kwargs.get('batchsize')

        if bool(start_date) is not bool(end_date):
            self.stdout.write(
                'Both start and end date must be specified or none of them'
            )
            return

        filter_kwargs = {}

        if start_date and end_date:
            filter_kwargs['release__created__range'] = (start_date, end_date)

        songs = (
            Song.objects.filter(**filter_kwargs)
            .select_related('release', 'release__user')
            .exclude(royalty_splits__isnull=False)
            .values('id', 'release__user_id', 'release__created')
        )

        self.stdout.write('Start migrating splits for %s songs' % songs.count())
        self.create_splits_from_deals(songs, batch_size)
        self.stdout.write('Completed migrating splits for releases')

    def create_splits_from_deals(self, songs, batch_size=10000):
        today = date.today()
        rate = Decimal('1.00')
        song_count = len(songs)

        for idx, song_chunk in enumerate(chunks(songs, batch_size), 1):
            royaltysplit_objs = []

            for song in song_chunk:
                royaltysplit_objs.append(
                    RoyaltySplit(
                        user_id=int(song['release__user_id']),
                        song_id=int(song['id']),
                        rate=rate,
                        status=RoyaltySplit.STATUS_ACTIVE,
                        start_date=song['release__created'].date(),
                    )
                )

            RoyaltySplit.objects.bulk_create(royaltysplit_objs, batch_size=batch_size)

            self.stdout.write(
                'Processed %s splits' % min((idx * batch_size), song_count)
            )

        self.stdout.write('Created %s splits' % song_count)
