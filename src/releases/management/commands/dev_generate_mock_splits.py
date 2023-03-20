from decimal import Decimal

from django.core.management.base import BaseCommand

from releases.models import RoyaltySplit
from releases.tests.factories import RoyaltySplitFactory


class Command(BaseCommand):
    help = """
    Generate splits for testing. Never run this in PROD! Only in dev/review/staging.
    """

    def add_arguments(self, parser):
        parser.add_argument(
            "--user_id", type=int, help="Generate splits for this user_id"
        )
        parser.add_argument(
            "--split_ids",
            nargs="+",
            type=int,
            help="Generate splits with these split_ids",
        )

    def handle(self, *args, **kwargs):
        user_id = kwargs.get("user_id")
        split_ids = kwargs.get("split_ids")

        if user_id is None or split_ids is None:
            self.stdout.write("You need to specify both user_id and split_ids.")

        for split_id in split_ids:
            RoyaltySplitFactory(
                id=split_id,
                user_id=user_id,
                revision=1,
                status=RoyaltySplit.STATUS_ACTIVE,
                rate=Decimal("1.00"),
                is_locked=False,
                is_owner=True,
                start_date=None,
                end_date=None,
            )

        self.stdout.write(
            "Split with ids %s created for user_id %s" % (split_ids, user_id)
        )
