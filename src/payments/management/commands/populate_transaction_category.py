from django.core.management.base import BaseCommand

from payments.models import PaymentTransaction
from subscriptions.models import Subscription


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            dest='is_dry_run',
            action='store_true',
            help='Just print operations, do not update',
            default=False,
        )

    def handle(self, *args, **kwargs):
        self.is_dry_run = kwargs['is_dry_run']
        self.action = self.is_dry_run and 'Would set' or 'Setting'

        for subscription in Subscription.objects.iterator():
            initial = (
                subscription.paymenttransaction_set.filter(
                    status=PaymentTransaction.STATUS_APPROVED
                )
                .order_by('created')
                .first()
            )
            if not initial:
                print(
                    f'Subscription {subscription} has no approved transactions, skipping'
                )
                continue

            self._set_category(initial, PaymentTransaction.CATEGORY_INITIAL)
            renewals = list(
                subscription.paymenttransaction_set.exclude(pk=initial.pk).order_by(
                    'created'
                )
            )

            if len(renewals) > 0:
                renewal = renewals[0]
                self._set_category(renewal, PaymentTransaction.CATEGORY_RENEWAL)
                paid_until = renewal.paid_until

                for payment in renewals[1:]:
                    if payment.paid_until == paid_until:
                        self._set_category(payment, PaymentTransaction.CATEGORY_RETRY)
                    else:
                        self._set_category(payment, PaymentTransaction.CATEGORY_RENEWAL)
                        paid_until = payment.paid_until

    def _set_category(self, payment, category):
        payment.category = category
        print(
            '%s category to %s for PaymentTransaction %s'
            % (self.action, payment.get_category_display(), payment)
        )
        if not self.is_dry_run:
            payment.save()
