import json
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import patch

import responses
from django.core.management import call_command
from django.urls import reverse
from freezegun import freeze_time

from amuse.tests.test_api.base import API_V4_ACCEPT_VALUE, AmuseAPITestCase
from amuse.tests.test_vendor.test_adyen.base import AdyenBaseTestCase
from amuse.tests.test_vendor.test_adyen.helpers import (
    mock_payment_details,
    mock_payment_response,
)
from amuse.vendor.adyen.helpers import convert_to_end_of_the_day
from countries.tests.factories import CountryFactory
from payments.models import PaymentMethod, PaymentTransaction
from subscriptions.models import Subscription
from subscriptions.tests.factories import SubscriptionFactory, SubscriptionPlanFactory
from users.tests.factories import UserFactory
from amuse.settings.constants import NONLOCALIZED_PAYMENTS_COUNTRY


class IntegrationBaseTestCase(AmuseAPITestCase, AdyenBaseTestCase):
    def setUp(self):
        super().setUp()
        self.country = CountryFactory(code='SE', is_adyen_enabled=True)
        self.url = reverse('create-adyen-subscription')
        self.client.credentials(HTTP_ACCEPT=API_V4_ACCEPT_VALUE)

    def _create_subscription(self, user, plan_id):
        self.client.force_authenticate(user)
        self.user = user
        self._add_checkout_response('Authorised')

        self.client.post(
            self.url,
            {
                'country': self.country.code,
                'plan': plan_id,
                'payment_details': mock_payment_details(),
            },
            format='json',
        ).json()
        return user.current_subscription()


class RenewalIntegrationTest(IntegrationBaseTestCase):
    @responses.activate
    def setUp(self):
        super().setUp()

        self.user_monthly = UserFactory(country=self.country.code)
        self.user_yearly = UserFactory(country=self.country.code)
        self.user_free = UserFactory(country=self.country.code)

        self.plan_monthly = SubscriptionPlanFactory(
            name="Pro Monthly", price=Decimal("4.99"), period=1, trial_days=0
        )
        self.plan_yearly = SubscriptionPlanFactory(
            name="Pro Yearly", price=Decimal("49.99"), period=12, trial_days=0
        )
        self.plan_free = SubscriptionPlanFactory(
            name="Pro Free VIP", price=Decimal("0.0"), period=None, is_public=False
        )

        self._add_country_check_response(self.country.code)

        with freeze_time("2019-01-01"):
            self.subscription_monthly = self._create_subscription(
                self.user_monthly, self.plan_monthly.id
            )
        with freeze_time("2019-01-15"):
            self.subscription_yearly = self._create_subscription(
                self.user_yearly, self.plan_yearly.id
            )

        self.subscription_free = SubscriptionFactory(
            user=self.user_free, plan=self.plan_free, valid_from=date(2019, 2, 28)
        )

    @responses.activate
    def test_renewal_renews_subscriptions_correctly_over_time(self):
        assert Subscription.objects.count() == 3
        assert PaymentTransaction.objects.count() == 2

        responses.add(
            responses.POST,
            "https://checkout-test.adyen.com/v49/payments",
            json.dumps(mock_payment_response(self.user_monthly)),
            status=200,
        )

        # Should not renew any subscriptions
        with freeze_time("2019-01-31"):
            call_command('renew_adyen_subscriptions', live_run=True)

        self._refresh_subscriptions()

        assert Subscription.objects.count() == 3
        assert PaymentTransaction.objects.count() == 2

        # Should renew the monthly subscription
        with freeze_time("2019-02-01"):
            call_command('renew_adyen_subscriptions', live_run=True)

        self._refresh_subscriptions()

        assert Subscription.objects.count() == 3
        self._assert_transaction_count(monthly_count=2, yearly_count=1, free_count=0)

        assert self.subscription_monthly.updated == datetime(
            2019, 2, 1, 0, 0, tzinfo=timezone.utc
        )

        monthly_transaction = self.subscription_monthly.paymenttransaction_set.last()

        assert monthly_transaction.paid_until == convert_to_end_of_the_day(
            date(2019, 3, 1)
        )

        # Should not renew any subscriptions
        with freeze_time("2019-02-02"):
            call_command('renew_adyen_subscriptions', live_run=True)

        self._refresh_subscriptions()

        assert Subscription.objects.count() == 3
        self._assert_transaction_count(monthly_count=2, yearly_count=1, free_count=0)

        # Should renew monthly subscription every month 2019-03-01 to 2020-01-01
        year = 2019
        for month in range(3, 14):
            if month == 13:
                year = 2020
                month = 1

            with freeze_time("%s-%02d-01" % (year, month)):
                call_command('renew_adyen_subscriptions', live_run=True)

        self._refresh_subscriptions()

        assert Subscription.objects.count() == 3
        self._assert_transaction_count(monthly_count=13, yearly_count=1, free_count=0)

        assert self.subscription_monthly.updated == datetime(
            2020, 1, 1, 0, 0, tzinfo=timezone.utc
        )
        assert self.subscription_yearly.updated == datetime(
            2019, 1, 15, 0, 0, tzinfo=timezone.utc
        )

        monthly_transaction = self.subscription_monthly.paymenttransaction_set.last()
        assert monthly_transaction.paid_until == convert_to_end_of_the_day(
            date(2020, 2, 1)
        )

        # Should only renew the yearly subscription
        with freeze_time("2020-01-15"):
            call_command('renew_adyen_subscriptions', live_run=True)

        self._refresh_subscriptions()

        assert Subscription.objects.count() == 3
        self._assert_transaction_count(monthly_count=13, yearly_count=2, free_count=0)

        assert self.subscription_monthly.updated == datetime(
            2020, 1, 1, 0, 0, tzinfo=timezone.utc
        )
        assert self.subscription_yearly.updated == datetime(
            2020, 1, 15, 0, 0, tzinfo=timezone.utc
        )

        yearly_transaction = self.subscription_yearly.paymenttransaction_set.last()
        assert yearly_transaction.paid_until == convert_to_end_of_the_day(
            date(2021, 1, 15)
        )

    def _refresh_subscriptions(self):
        self.subscription_monthly.refresh_from_db()
        self.subscription_yearly.refresh_from_db()
        self.subscription_free.refresh_from_db()

    def _assert_transaction_count(self, monthly_count, yearly_count, free_count):
        assert self.subscription_monthly.paymenttransaction_set.count() == monthly_count
        assert self.subscription_yearly.paymenttransaction_set.count() == yearly_count
        assert self.subscription_free.paymenttransaction_set.count() == free_count


class RenewalGracePeriodIntegrationTest(IntegrationBaseTestCase):
    @responses.activate
    def setUp(self):
        super().setUp()
        self.plan = SubscriptionPlanFactory(
            trial_days=30, period=1, grace_period_days=7
        )
        self.user = UserFactory()

        self._add_country_check_response(self.country.code)
        self.subscription = self._create_subscription(self.user, self.plan.pk)

    @responses.activate
    def test_grace_period(self):
        self._add_checkout_response('Refused')

        with freeze_time(
            self.subscription.latest_payment().paid_until + timedelta(days=1)
        ):
            call_command('renew_adyen_subscriptions', live_run=True)

        # Should have grace period for paid subscription
        self._assert_subscription_status()
        self.assertEqual(PaymentTransaction.objects.count(), 2)
        self.assertEqual(
            self.subscription.latest_payment(allow_failed=True).category,
            PaymentTransaction.CATEGORY_RENEWAL,
        )
        self.assertEqual(
            self.subscription.grace_period_until,
            self.subscription.allowed_grace_period_until(),
        )

        # Next day bill_changed_adyen_subscriptions runs again
        responses.reset()
        self._add_checkout_response('Refused')

        with freeze_time(
            self.subscription.latest_payment().paid_until + timedelta(days=2)
        ):
            call_command('renew_adyen_subscriptions', live_run=True)

        # Should still have grace period for paid subscription
        self._assert_subscription_status()
        self.assertEqual(PaymentTransaction.objects.count(), 3)
        self.assertEqual(
            self.subscription.latest_payment(allow_failed=True).category,
            PaymentTransaction.CATEGORY_RETRY,
        )

        # When grace period is passed bill_changed_adyen_subscriptions runs
        responses.reset()
        self._add_checkout_response('Refused')

        with freeze_time(
            self.subscription.latest_payment().paid_until
            + timedelta(days=self.plan.grace_period_days + 10)
        ):
            call_command('renew_adyen_subscriptions', live_run=True)

        # After grace period, should expire paid subscription
        self._assert_subscription_status(Subscription.STATUS_EXPIRED)
        self.assertEqual(PaymentTransaction.objects.count(), 4)

    def _assert_subscription_status(
        self, subscription_status=Subscription.STATUS_GRACE_PERIOD
    ):
        self.subscription.refresh_from_db()
        self.assertEqual(self.subscription.status, subscription_status)


class SubscriptionPaymentMethodIntegrationTest(IntegrationBaseTestCase):
    @responses.activate
    def setUp(self):
        super().setUp()
        self.payment_method_url = reverse('update-current-payment-method')
        self.plan = SubscriptionPlanFactory(
            trial_days=30, period=1, grace_period_days=7
        )
        self.yearly_plan = SubscriptionPlanFactory(
            trial_days=60, period=12, grace_period_days=7
        )

        self.user = UserFactory()

        self._add_country_check_response(self.country.code)
        self.subscription = self._create_subscription(self.user, self.plan.pk)

    @responses.activate
    @patch('amuse.api.base.views.payment_methods.subscription_payment_method_changed')
    @patch('amuse.api.base.views.subscription.subscription.subscription_changed')
    def test_changing_payment_method_does_not_create_new_subscriptions(
        self, mocked_subscription_changed, mocked_payment_method_changed
    ):
        # Change subscription payment details
        payload = {
            'country': self.country.code,
            'payment_details': mock_payment_details(),
        }
        self._add_country_check_response(self.country.code)
        self._add_checkout_response(
            'Authorised', additional_data={'cardSummary': '9999', 'paymentMethod': 'mc'}
        )
        self.client.put(self.payment_method_url, payload, format='json')
        mocked_payment_method_changed.assert_called_once_with(
            self.subscription, '', '127.0.0.1'
        )

        self._assert_subscription_status()
        self.assertEqual(PaymentMethod.objects.count(), 2)
        self.assertEqual(PaymentTransaction.objects.count(), 2)
        self.assertEqual(self.subscription.payment_method.summary, '9999')
        self.assertEqual(self.subscription.payment_method.method, 'mc')

        # Running cronjob now should not change anything
        with freeze_time(self.subscription.created + timedelta(days=1)):
            call_command('renew_adyen_subscriptions', live_run=True)

        self.assertEqual(Subscription.objects.count(), 1)
        self._assert_subscription_status()

        # Change subscription plan
        url = reverse('update-current-subscription-plan')
        self.client.put(url, {'plan': self.yearly_plan.pk})
        self._assert_subscription_status()
        mocked_subscription_changed.assert_called_once_with(
            self.subscription,
            self.plan,
            self.yearly_plan,
            '',
            '127.0.0.1',
            self.country.code,
        )

        # Running cronjob now should not change anything
        with freeze_time(self.subscription.created + timedelta(days=2)):
            call_command('renew_adyen_subscriptions', live_run=True)

        self._assert_subscription_status()
        self.assertEqual(Subscription.objects.count(), 1)
        self.assertEqual(self.subscription.plan_id, self.yearly_plan.pk)

    def _assert_subscription_status(self):
        self.subscription.refresh_from_db()
        self.assertEqual(self.subscription.status, Subscription.STATUS_ACTIVE)
