from django.core.management.base import BaseCommand

from payments.models import PaymentMethod
from subscriptions.models import Subscription


class Command(BaseCommand):
    def handle(self, *args, **kwargs):
        rows = Subscription.objects.filter(
            payment_method__isnull=False,
            payment_method__external_recurring_id__isnull=True,
            provider=Subscription.PROVIDER_ADYEN,
        ).values_list(
            'id',
            'payment_method__id',
            'payment_method__user_id',
            'payment_method__method',
            'payment_method__summary',
        )

        broken_payment_method_ids = []

        for r in rows:
            try:
                payment_method = PaymentMethod.objects.get(
                    external_recurring_id__isnull=False,
                    user_id=r[2],
                    method=r[3],
                    summary=r[4],
                )

                subscription = Subscription.objects.get(pk=r[0])
                subscription.payment_method = payment_method
                subscription.save()
                broken_payment_method_ids.append(r[1])
            except PaymentMethod.DoesNotExist:
                print('No valid PaymentMethod found for subscription %s' % r[0])

        PaymentMethod.objects.filter(pk__in=broken_payment_method_ids).delete()
