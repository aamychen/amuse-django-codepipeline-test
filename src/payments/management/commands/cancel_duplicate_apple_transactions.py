from django.core.management.base import BaseCommand
from django.db import connection

from payments.models import PaymentTransaction


DUPLICATE_IDS_SQL = '''
SELECT
    external_transaction_id
FROM
    payments_paymenttransaction AS p
    JOIN subscriptions_subscription AS s ON p.subscription_id = s.id
WHERE
    s.provider = 2
GROUP BY
    external_transaction_id
HAVING
    COUNT(*) > 1;
'''


class Command(BaseCommand):
    def handle(self, *args, **kwargs):
        with connection.cursor() as cursor:
            cursor.execute(DUPLICATE_IDS_SQL)
            rows = cursor.fetchall()
        duplicate_transaction_external_ids = [r[0] for r in rows]

        print(
            'Found %s duplicates: %s'
            % (
                len(duplicate_transaction_external_ids),
                ', '.join(duplicate_transaction_external_ids),
            )
        )

        for external_id in duplicate_transaction_external_ids:
            # Keep first PaymentTransaction when duplicates exist
            duplicate_ids = (
                PaymentTransaction.objects.filter(external_transaction_id=external_id)
                .order_by('created')
                .values_list('pk', flat=True)[1:]
            )

            PaymentTransaction.objects.filter(pk__in=duplicate_ids).update(
                status=PaymentTransaction.STATUS_CANCELED
            )
            print(
                '%s set ids %s to STATUS_CANCELED'
                % (external_id, ', '.join(map(str, duplicate_ids)))
            )
