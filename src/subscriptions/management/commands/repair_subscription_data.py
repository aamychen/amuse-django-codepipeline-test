import sys
from django.db import connection
from django.core.management.base import BaseCommand
from amuse.logging import logger
from subscriptions.models import Subscription
from payments.models import PaymentTransaction, PaymentMethod
from amuse.vendor.adyen.base import AdyenGetRecurringInfo


class Command(BaseCommand):
    '''
    Collection of tools for keeping subscriptions and payment data consistent.
    '''

    help = (
        'Repair subscription data'
        'Usage: python manage.py repair_subscription_data [args]'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--fix_payment_methods',
            help="Fill missing external_recurring_id for Adyen",
            type=bool,
            default=True,
            required=False,
        )

    def handle(self, *args, **kwargs):
        fix_payment_methods = kwargs.get('fix_payment_methods')
        if fix_payment_methods:
            self.fix_adyen_payment_methods()

    def fix_adyen_payment_methods(self):
        client = AdyenGetRecurringInfo()
        try:
            cursor = connection.cursor()
            cursor.execute(
                "select ss.user_id, ss.id, pp.external_transaction_id, pm.id as pm_id "
                "from payments_paymentmethod pm "
                "join payments_paymenttransaction pp on pp.payment_method_id=pm.id "
                "join subscriptions_subscription ss on ss.payment_method_id=pm.id "
                "and pm.external_recurring_id is null "
                "and pp.external_transaction_id is not null "
                "and pp.status=%s "
                "and ss.provider=%s "
                "and ss.status in (%s,%s) ",
                [
                    PaymentTransaction.STATUS_APPROVED,
                    Subscription.PROVIDER_ADYEN,
                    Subscription.STATUS_ACTIVE,
                    Subscription.STATUS_GRACE_PERIOD,
                ],
            )
            data = cursor.fetchall()
            for row in data:
                try:
                    paymet_method = PaymentMethod.objects.get(id=row[3])
                    data = client.get_recurring_info(row[0])
                    last_info = data['details'][-1]['RecurringDetail']
                    paymet_method.external_recurring_id = last_info[
                        'recurringDetailReference'
                    ]
                    paymet_method.method = last_info['variant']
                    paymet_method.save()
                except Exception as e:
                    logger.warning(
                        f'Error updating Payment Method {paymet_method.id} error={e}'
                    )
                    continue
            cursor.close()
        except Exception as e:
            logger.warning(f'DB error while fixing adyen payment method data error={e}')
