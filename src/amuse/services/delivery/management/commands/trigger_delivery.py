from datetime import datetime

from django.core.management.base import BaseCommand

from amuse.services.delivery.helpers import deliver_batches
from releases.models import Release
from users.models import User


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument(
            "--release_ids",
            type=int,
            nargs="+",
            help="Space-separated release_ids to deliver",
        )
        parser.add_argument(
            "--type",
            type=str,
            required=True,
            help="Specify delivery type. insert, update or takedown",
        )
        parser.add_argument(
            "--status_ids",
            type=int,
            nargs="+",
            default=Release.VALID_DELIVERY_STATUS_SET,
            help="Specify release status_ids. Example: 4 for Approved etc.",
        )
        parser.add_argument(
            "--stores",
            type=str,
            nargs="+",
            default=[],
            help="Space-separated store internal_names to deliver to. Skips releases that does not include the specified stores",
        )
        parser.add_argument(
            "--override_stores",
            action="store_true",
            default=False,
            help="Bypass dynamic Fuga/DD feed selection logic",
        )
        parser.add_argument(
            "--batchsize",
            type=int,
            default=None,
            help="Specify how many releases to include in a batch",
        )
        parser.add_argument(
            "--delay",
            type=float,
            default=0,
            help="Specify delay between triggering each batch",
        )
        parser.add_argument(
            "--dryrun",
            action="store_true",
            default=False,
            help="Only print what will be processed",
        )
        parser.add_argument(
            "--user_id",
            type=int,
            default=None,
            help="Specify the ID of the user who is triggering this delivery",
        )

    def handle(self, *args, **kwargs):
        start_time = datetime.now()

        release_ids = kwargs["release_ids"]
        delivery_type = kwargs["type"]
        status_ids = kwargs["status_ids"]
        stores = kwargs["stores"]
        override_stores = kwargs["override_stores"]
        batchsize = kwargs["batchsize"]
        delay = kwargs["delay"]
        dryrun = kwargs["dryrun"]
        user_id = kwargs["user_id"]

        if not release_ids:
            self.stdout.write("You need to specify release_ids")
            return False

        releases = Release.get_releases_by_id(status_ids, release_ids, stores)

        user = None

        if user_id:
            user = User.objects.get(id=user_id)

        deliver_batches(
            releases=releases,
            delivery_type=delivery_type,
            stores=stores,
            override_stores=override_stores,
            batchsize=batchsize,
            delay=delay,
            dryrun=dryrun,
            user=user,
        )

        self.stdout.write("Time to process: %s" % (datetime.now() - start_time))
