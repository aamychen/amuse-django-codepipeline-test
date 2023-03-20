import logging

from django.core.management.base import BaseCommand

from payments.models import PaymentTransaction
from subscriptions.models import Subscription
from subscriptions.vendor.google import helpers

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = """
    Every now and then Google replaces the original subscription with a new one.
    Our backend code did handle this scenario properly. Some payments are wrongly marked
    with status error, and some free trial subscriptions are not marked as free trials.

    This command will identify such payments and subscriptions, and will fix them.

    """

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            dest='is_dry_run',
            help='Just print, do not update',
            action='store_true',
            default=False,
        )

        parser.add_argument(
            '--fix-payments',
            nargs='+',
            type=int,
            help='Single/multiple payment transaction ids separated by space. Example: 1 2 3 4',
        )

    def handle(self, *args, **kwargs):
        is_dry_run = kwargs['is_dry_run']
        fix_payments = kwargs['fix_payments']

        payments = PaymentTransaction.objects.prefetch_related('subscription').filter(
            subscription__provider=Subscription.PROVIDER_GOOGLE,
            amount=0,
            type=PaymentTransaction.TYPE_PAYMENT,
        )

        if fix_payments:
            print("Filtering by payments: ", fix_payments)
            payments = payments.filter(pk__in=fix_payments)

        print(f"is dry run {is_dry_run}")
        print(
            f"#\tsub_id\ttx_id\tamount\tstatus\ttype\tcat.\tpaid_until\tFT from\tFT until"
        )
        for i, p in enumerate(payments.all()):
            self.info(f"#{i} Before", p)
            expiry = int(p.external_payment_response['expiryTimeMillis'])
            if p.amount == 0:
                p.subscription.free_trial_from = helpers.convert_msepoch_to_dt(expiry)
                p.subscription.free_trial_until = p.paid_until
                p.type = PaymentTransaction.TYPE_FREE_TRIAL

            p.category = PaymentTransaction.CATEGORY_RENEWAL
            self.info(f"#{i} After", p)

            if is_dry_run == False:
                p.subscription.save()
                p.save()

    def info(self, prefix: str, p: PaymentTransaction):
        print(
            f"{prefix}\t{p.subscription_id}\t{p.id}\t{p.amount}\t{p.get_status_display()}\t{p.get_type_display()}\t{p.get_category_display()}\t{p.paid_until}\t{p.subscription.free_trial_from}\t{p.subscription.free_trial_until}"
        )
