from unittest.mock import patch

from dateutil.relativedelta import relativedelta
from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from payments.models import PaymentTransaction
from payments.tests.factories import PaymentTransactionFactory
from subscriptions.tests.factories import SubscriptionFactory, SubscriptionPlanFactory


class PopulateTransactionCategoryTestCase(TestCase):
    @patch('amuse.tasks.zendesk_create_or_update_user')
    def setUp(self, mock_zendesk):
        plan = SubscriptionPlanFactory(period=1, trial_days=0)
        subscription = SubscriptionFactory(plan=plan)
        user = subscription.user

        paid_until = timezone.now()
        self.payment_1 = PaymentTransactionFactory(
            paid_until=paid_until,
            subscription=subscription,
            status=PaymentTransaction.STATUS_APPROVED,
            user=user,
        )
        self.payment_2 = PaymentTransactionFactory(
            paid_until=paid_until + relativedelta(months=plan.period),
            status=PaymentTransaction.STATUS_DECLINED,
            subscription=subscription,
            user=user,
        )
        self.payment_3 = PaymentTransactionFactory(
            paid_until=paid_until + relativedelta(months=plan.period),
            status=PaymentTransaction.STATUS_DECLINED,
            subscription=subscription,
            user=user,
        )
        self.payment_4 = PaymentTransactionFactory(
            paid_until=paid_until + relativedelta(months=plan.period * 2),
            status=PaymentTransaction.STATUS_APPROVED,
            subscription=subscription,
            user=user,
        )

    def test_category_populated(self):
        call_command('populate_transaction_category')
        self.payment_1.refresh_from_db()
        self.payment_2.refresh_from_db()
        self.payment_3.refresh_from_db()
        self.payment_4.refresh_from_db()

        self.assertEqual(self.payment_1.category, PaymentTransaction.CATEGORY_INITIAL)
        self.assertEqual(self.payment_2.category, PaymentTransaction.CATEGORY_RENEWAL)
        self.assertEqual(self.payment_3.category, PaymentTransaction.CATEGORY_RETRY)
        self.assertEqual(self.payment_4.category, PaymentTransaction.CATEGORY_RENEWAL)
