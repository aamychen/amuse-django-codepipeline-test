from dateutil.parser import isoparse
from django.core.management.base import BaseCommand

from releases.models import Release, Store


class Command(BaseCommand):
    help = 'Migrate Release.excluded_stores to Release.stores'

    def add_arguments(self, parser):
        parser.add_argument('--start-date', type=isoparse, help='1900-01-01')
        parser.add_argument('--end-date', type=isoparse, help='2021-12-31')
        parser.add_argument(
            '--batchsize', type=int, help='iterator batch size', default=10000
        )

    def handle(self, *args, **kwargs):
        start_date = kwargs.get('start_date', None)
        end_date = kwargs.get('end_date', None)
        batch_size = kwargs.get('batchsize')

        if bool(start_date) is not bool(end_date):
            self.stdout.write('Specify both start and end date or none of them')
            exit(1)

        filter_kwargs = {}

        if start_date and end_date:
            filter_kwargs['created__range'] = (start_date, end_date)

        releases = Release.objects.filter(**filter_kwargs)
        store_ids = set(Store.objects.active().values_list('pk', flat=True))

        print('Migrating %s releases' % releases.count())
        for release_id in releases.values_list('pk', flat=True).iterator(batch_size):
            print('Migrating %s' % release_id)
            release = Release(pk=release_id)
            release_store_ids = list(
                store_ids - set(release.excluded_stores.values_list('pk', flat=True))
            )
            release.stores.set(release_store_ids)
