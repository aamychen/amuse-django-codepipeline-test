from datetime import timedelta

import responses
from dateutil.relativedelta import relativedelta
from django.utils import timezone

from amuse.utils import CLIENT_WEB
from amuse.tests.helpers import add_zendesk_mock_post_response
from amuse.tests.test_vendor.test_adyen.base import AdyenBaseTestCase
from amuse.tests.test_vendor.test_adyen.helpers import mock_payment_details
from amuse.vendor.adyen import create_subscription
from countries.tests.factories import CountryFactory
from payments.models import PaymentTransaction
from payments.tests.factories import PaymentTransactionFactory
from subscriptions.helpers import renew_adyen_subscriptions
from subscriptions.models import Subscription
from subscriptions.tests.factories import SubscriptionFactory, SubscriptionPlanFactory
from users.tests.factories import UserFactory, UserMetadataFactory


class TrialEndedTestCase(AdyenBaseTestCase):
    @responses.activate
    def setUp(self):
        add_zendesk_mock_post_response()
        now = timezone.now()
        self.today = now.date()
        self.plan = SubscriptionPlanFactory(trial_days=90, period=12)
        purchased_at = self.today - timedelta(days=91)
        trial_valid_until = self.today - timedelta(days=1)
        self.user = UserFactory()
        UserMetadataFactory(user=self.user, pro_trial_expiration_date=trial_valid_until)
        self.subscription = SubscriptionFactory(
            plan=self.plan,
            provider=Subscription.PROVIDER_ADYEN,
            status=Subscription.STATUS_ACTIVE,
            user=self.user,
            valid_from=purchased_at,
        )
        paid_until = now - timedelta(days=1)
        payment = PaymentTransactionFactory(
            amount=0,
            paid_until=paid_until,
            subscription=self.subscription,
            type=PaymentTransaction.TYPE_AUTHORISATION,
            user=self.user,
        )
        payment.created = now - timedelta(days=91)
        payment.save()

    @responses.activate
    def test_first_payment_after_trial(self):
        self.subscription.payment_method.external_recurring_id = '8415732066637761'
        self.subscription.payment_method.save()
        self._add_checkout_response('Authorised')
        renew_adyen_subscriptions(is_dry_run=False)

        self.assertEqual(PaymentTransaction.objects.count(), 2)
        self._assert_payment_and_subscription(
            payment_status=PaymentTransaction.STATUS_APPROVED,
            subscription_user_id=self.user.pk,
            subscription_status=Subscription.STATUS_ACTIVE,
        )
        self.assertEqual(
            self.subscription.paid_until, self.today + relativedelta(months=12, days=-1)
        )

    @responses.activate
    def test_when_first_payment_after_trial_fails_trial_ends(self):
        self._add_checkout_response('Refused')
        renew_adyen_subscriptions(is_dry_run=False)

        self.assertEqual(PaymentTransaction.objects.count(), 2)
        self._assert_payment_and_subscription(
            payment_status=PaymentTransaction.STATUS_DECLINED,
            subscription_user_id=self.user.pk,
            subscription_status=Subscription.STATUS_EXPIRED,
        )
