from datetime import date
from decimal import Decimal

from dateutil.parser import isoparse
from django.core.management.base import BaseCommand

from amuse.utils import chunks
from releases.models import RoyaltySplit


class Command(BaseCommand):
    help = 'Populate is_owner for RoyaltySplit'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            dest='is_dry_run',
            action='store_true',
            help='Just print, do not update',
            default=False,
        )
        parser.add_argument('--start-date', type=isoparse, help='2019-01-01')
        parser.add_argument('--end-date', type=isoparse, help='2019-12-31')
        parser.add_argument(
            '--release_ids',
            nargs='+',
            type=int,
            help='Single/multiple release_ids separated by space. Example: 1 2 3 4',
        )
        parser.add_argument(
            '--batchsize', type=int, help='bulk_create batch_size', default=10000
        )

    def handle(self, *args, **kwargs):
        batch_size = kwargs['batchsize']
        is_dry_run = kwargs['is_dry_run']
        start_date = kwargs.get('start_date')
        end_date = kwargs.get('end_date')
        release_ids = kwargs.get('release_ids')
        filter_kwargs = {}

        if bool(start_date) is not bool(end_date):
            self.stdout.write(
                'Both start and end date must be specified or none of them'
            )
            return
        elif start_date and end_date:
            filter_kwargs['song__release__created__range'] = (start_date, end_date)

        if release_ids:
            filter_kwargs["song__release_id__in"] = release_ids

        filter_kwargs["is_owner"] = False
        filter_kwargs["is_locked"] = False

        if is_dry_run:
            print("Start DRY RUN")
        else:
            print("Start REAL RUN")

        royalty_splits_iterator = (
            RoyaltySplit.objects.filter(**filter_kwargs)
            .select_related("song", "song__release")
            .iterator(batch_size)
        )

        for split in royalty_splits_iterator:
            is_owner = split._get_is_owner()

            if is_owner:
                if not is_dry_run:
                    split.is_owner = is_owner
                    split.save()
                print(
                    "SET is_owner to True for split_id %s user_id %s"
                    % (split.pk, split.user_id)
                )

        if is_dry_run:
            print("Finished DRY RUN")
        else:
            print("Finished REAL RUN")
