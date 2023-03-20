from django.core.management.base import BaseCommand

from subscriptions.helpers import renew_adyen_subscriptions


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument(
            '--live-run',
            dest='is_live_run',
            action='store_true',
            help='Actually renew expired subscriptions',
            default=False,
        )

    def handle(self, *args, **kwargs):
        renew_adyen_subscriptions(is_dry_run=not kwargs['is_live_run'])
