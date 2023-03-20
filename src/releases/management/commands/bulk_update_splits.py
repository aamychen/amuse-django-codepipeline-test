from django.core.management.base import BaseCommand

from releases.models import RoyaltySplit


class Command(BaseCommand):
    help = """
        Sets start_date=None for revision 1 royalty splits. This is
        safe to re-run.
        """

    def handle(self, *args, **kwargs):
        splits = RoyaltySplit.objects.filter(
            start_date__isnull=False, revision=1, is_locked=False
        )
        splits_count = splits.count()

        self.stdout.write('Selected %s royalty splits to update' % splits_count)

        splits.update(start_date=None)

        self.stdout.write('Finished updating  %s royalty splits' % splits_count)
