import time
from django.core.management.base import BaseCommand
from amuse.vendor.zendesk.api import update_users
from users.models.user import User
from requests.exceptions import HTTPError


class Command(BaseCommand):
    help = 'Bulk-refreshes all existing Zendesk users according to content of Jarvis.'

    BATCH_SIZE = 100
    INTERVAL_SECONDS = 0.5

    def add_arguments(self, parser):
        parser.add_argument(
            '-s',
            '--start',
            type=int,
            help='An integer user id to start the update from',
        )
        parser.add_argument(
            '-e', '--end', type=int, help='The largest id of users being processed'
        )
        parser.add_argument('-bs', '--batchsize', type=int, help='The batch size')

    def handle(self, *args, **options):
        users_query = User.objects.filter(zendesk_id__isnull=False)

        start_id = options['start']
        if start_id:
            users_query = users_query.filter(pk__gte=start_id)

        end_id = options['end']
        if end_id:
            if start_id and start_id > end_id:
                self.stdout.write(
                    self.style.WARNING(
                        'Passed start id is greater than the end id. Breaking this execution...'
                    )
                )
                return
            users_query = users_query.filter(pk__lte=end_id)

        batch_size = options['batchsize']
        if batch_size:
            if batch_size < 1:
                self.style.WARNING(
                    'Passed an invalid value of batch size. Breaking this execution...'
                )
                return
            if batch_size > self.BATCH_SIZE:
                self.style.WARNING(
                    f'Passed value of batch size is greater than Zendesk\'s limit: {self.BATCH_SIZE}. Breaking this execution...'
                )
                return
            self.BATCH_SIZE = batch_size

        self._update_users(users_query)

        self.stdout.write(self.style.SUCCESS('Users were successfully updated.'))

    def _update_users(self, users_queryset):
        total_users = users_queryset.count()

        import math

        num_batches = int(math.ceil(total_users / self.BATCH_SIZE))

        curr_batch_num = 1
        start_user_id = 0
        while True:
            self.stdout.write(
                f"Updating batch {curr_batch_num} out of {num_batches}..."
            )
            self.stdout.write(f"(start id: {start_user_id})")

            batch = users_queryset.filter(pk__gt=start_user_id).order_by("pk")[
                : self.BATCH_SIZE
            ]
            try:
                r = update_users(batch)
                r.raise_for_status()
            except HTTPError as http_err:
                self.stderr.write(self.style.ERROR(f'HTTP error occurred: {http_err}'))
                user_ids = [user.id for user in batch]
                self.stderr.write(f'(user id\'s: {user_ids})')

            if len(batch) < self.BATCH_SIZE:
                break
            start_user_id = batch[self.BATCH_SIZE - 1].id

            # Prevent throttling
            time.sleep(self.INTERVAL_SECONDS)

            curr_batch_num += 1
