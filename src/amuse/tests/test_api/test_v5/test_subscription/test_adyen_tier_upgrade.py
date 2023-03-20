from unittest.mock import patch

import responses
from dateutil.relativedelta import relativedelta
from django.urls import reverse
from django.utils import timezone
from rest_framework import status

from amuse.tests.test_api.base import AmuseAPITestCase
from amuse.tests.test_vendor.test_adyen.base import AdyenBaseTestCase
from amuse.tests.test_vendor.test_adyen.helpers import mock_payment_details
from amuse.vendor.adyen.helpers import convert_to_end_of_the_day
from countries.tests.factories import CountryFactory, CurrencyFactory
from payments.models import PaymentTransaction
from payments.tests.factories import PaymentTransactionFactory
from subscriptions.helpers import calculate_tier_upgrade_price
from subscriptions.models import Subscription, SubscriptionPlan
from subscriptions.tests.factories import (
    SubscriptionPlanFactory,
    SubscriptionFactory,
    PriceCardFactory,
)
from users.tests.factories import UserFactory


class UpgradeTierInfoViewTestCase(AmuseAPITestCase, AdyenBaseTestCase):
    @responses.activate
    def setUp(self):
        with patch("amuse.tasks.zendesk_create_or_update_user"):
            self.user = UserFactory()
        self.country = CountryFactory(is_adyen_enabled=True)
        self.currency = CurrencyFactory()
        self.plan = SubscriptionPlanFactory(
            countries=[self.country], currency=self.currency
        )
        self.old_plan = SubscriptionPlanFactory(
            tier=SubscriptionPlan.TIER_PLUS,
            countries=[self.country],
            currency=self.currency,
        )
        self.client.force_authenticate(self.user)
        self.url = reverse('adyen-tier-upgrade', args=(self.plan.pk,))

    def test_only_adyen_subscriptions_allowed(self):
        subscription = SubscriptionFactory(
            user=self.user,
            provider=Subscription.PROVIDER_IOS,
        )
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(
            str(response.data['detail']), 'Subscription Provider Mismatch Error'
        )

    def test_no_active_sub_raises_error(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(
            str(response.data['detail']), 'You have no active paid subscription.'
        )

    def test_bad_plan_id_raises_error(self):
        subscription = SubscriptionFactory(user=self.user)
        url = reverse('adyen-tier-upgrade', args=(self.plan.pk + 42069,))
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(
            str(response.data['detail']),
            'The specified Subscription Plan does not exist.',
        )

    def test_only_boost_to_pro_upgrades_allowed(self):
        plan = SubscriptionPlanFactory(tier=SubscriptionPlan.TIER_PRO)
        self.plan.tier = SubscriptionPlan.TIER_PLUS
        self.plan.save()
        subscription = SubscriptionFactory(user=self.user, plan=plan)
        url = reverse('adyen-tier-upgrade', args=(self.plan.pk,))
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(
            str(response.data[0]),
            'Upgrades are only possible from BOOST Tier to PRO Tier',
        )

    def test_same_tier_upgrades_not_allowed(self):
        plan = SubscriptionPlanFactory(tier=SubscriptionPlan.TIER_PRO)
        subscription = SubscriptionFactory(user=self.user, plan=plan)
        url = reverse('adyen-tier-upgrade', args=(self.plan.pk,))
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(
            str(response.data[0]),
            'Unable to upgrade tier, new and current tier are the same',
        )

    def test_price_calculation_error_if_no_transactions_present(self):
        subscription = SubscriptionFactory(user=self.user)
        plan = subscription.plan
        plan.tier = SubscriptionPlan.TIER_PLUS
        plan.save()
        url = reverse('adyen-tier-upgrade', args=(self.plan.pk,))
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn(
            f'No valid payments found for Subscription {subscription.pk}, unable to calculate Tier upgrade price',
            str(response.data[0]),
        )

    def test_price_calculation_return_data(self):
        subscription = SubscriptionFactory(user=self.user, plan=self.old_plan)
        transaction = PaymentTransactionFactory(
            subscription=subscription,
            country=self.country,
            plan=self.old_plan,
            currency=self.currency,
            paid_until=timezone.now() + timezone.timedelta(days=30),
        )
        transaction.created = timezone.now()
        transaction.save()
        url = reverse('adyen-tier-upgrade', args=(self.plan.pk,))
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertEqual(response.data['current_plan'], self.old_plan.pk)
        self.assertEqual(response.data['new_plan'], self.plan.pk)

        price, currency = calculate_tier_upgrade_price(subscription, self.plan)
        self.assertIn('upgrade_price', response.data)
        self.assertEqual(response.data['upgrade_price'], str(price))
        self.assertEqual(response.data['currency'], currency.code)
        self.assertEqual(
            response.data['upgrade_price_display'], f'{currency.code} {str(price)}'
        )


class UpgradeTierTestCase(AmuseAPITestCase, AdyenBaseTestCase):
    @responses.activate
    def setUp(self):
        with patch("amuse.tasks.zendesk_create_or_update_user"):
            self.user = UserFactory()
        self.country = CountryFactory(is_adyen_enabled=True)
        self.currency = CurrencyFactory()
        self.current_plan = SubscriptionPlanFactory(
            name='Old PLUS Plan',
            tier=SubscriptionPlan.TIER_PLUS,
            countries=[self.country],
            currency=self.currency,
        )
        self.subscription = SubscriptionFactory(user=self.user, plan=self.current_plan)
        self.transaction = PaymentTransactionFactory(
            plan=self.current_plan,
            subscription=self.subscription,
            country=self.country,
            currency=self.currency,
            paid_until=timezone.now() + relativedelta(years=1),
            created=timezone.now(),
        )
        self.plan = SubscriptionPlanFactory(
            name='New PRO Plan',
            tier=SubscriptionPlan.TIER_PRO,
            countries=[self.country],
            currency=self.currency,
        )
        self.client.force_authenticate(self.user)
        self.url = reverse(f'adyen-tier-upgrade', args=(self.plan.pk,))

    @responses.activate
    @patch('amuse.api.base.views.subscription.subscription.subscription_tier_upgraded')
    def test_create_subscription_is_successful(self, mocked_segment):
        price, currency = calculate_tier_upgrade_price(self.subscription, self.plan)

        self._add_country_check_response(self.country.code)
        self._add_checkout_response('Authorised')
        response = self.client.post(self.url)

        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.assertEqual(response.data, {"is_success": True})
        subscription = self.user.current_subscription()
        payment = subscription.latest_payment()

        self.assertEqual(payment.category, PaymentTransaction.CATEGORY_INITIAL)
        self.assertEqual(payment.status, PaymentTransaction.STATUS_APPROVED)
        self.assertEqual(payment.amount, price)
        self.assertEqual(
            payment.paid_until,
            convert_to_end_of_the_day(timezone.now())
            + relativedelta(months=self.plan.period),
        )
        self.assertEqual(payment.currency, currency)
        self.assertEqual(payment.country, self.country)
        self.assertEqual(payment.platform, PaymentTransaction.PLATFORM_WEB)
        self.assertEqual(payment.user, self.user)
        self.assertNotEqual(payment.subscription, self.subscription)
        self.assertEqual(payment.plan, self.plan)

        self.assertEqual(subscription.plan.tier, self.plan.tier)
        self.assertEqual(subscription.status, Subscription.STATUS_ACTIVE)
        self.assertEqual(subscription.provider, Subscription.PROVIDER_ADYEN)

        self.subscription.refresh_from_db()
        self.assertEqual(self.subscription.status, Subscription.STATUS_EXPIRED)
        self.assertEqual(self.subscription.paid_until, timezone.now().date())
        self.assertEqual(self.subscription.valid_until, timezone.now().date())
        self.assertEqual(self.user.tier, self.plan.tier)

        mocked_segment.assert_called_once_with(
            subscription,
            self.current_plan,
            '',
            '127.0.0.1',
            self.country.code,
        )

    @responses.activate
    @patch('amuse.api.base.views.subscription.subscription.subscription_tier_upgraded')
    def test_create_subscription_new_payment_info_is_successful(self, mocked_segment):
        url = self.url + '?use_existing_payment_info=false'
        price, currency = calculate_tier_upgrade_price(self.subscription, self.plan)

        self._add_country_check_response(self.country.code)
        self._add_checkout_response('Authorised')
        payment_details = mock_payment_details()

        web_user_agent = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:80.0) Gecko/20100101 Firefox/80.0'
        headers = {'HTTP_USER_AGENT': web_user_agent}
        response = self.client.post(
            url,
            {
                'country': self.country.code,
                'plan': self.plan.pk,
                'payment_details': payment_details,
            },
            format='json',
            **headers,
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.assertEqual(response.data, {"is_success": True})
        subscription = self.user.current_subscription()
        payment = subscription.latest_payment()

        self.assertEqual(payment.category, PaymentTransaction.CATEGORY_INITIAL)
        self.assertEqual(payment.status, PaymentTransaction.STATUS_APPROVED)
        self.assertEqual(payment.amount, price)
        self.assertEqual(
            payment.paid_until.date(),
            (timezone.now() + relativedelta(months=self.plan.period)).date(),
        )
        self.assertEqual(payment.currency, currency)
        self.assertEqual(payment.country, self.country)
        self.assertEqual(payment.platform, PaymentTransaction.PLATFORM_WEB)
        self.assertEqual(payment.user, self.user)
        self.assertNotEqual(payment.subscription, self.subscription)
        self.assertEqual(payment.plan, self.plan)

        self.assertEqual(subscription.plan.tier, self.plan.tier)
        self.assertEqual(subscription.status, Subscription.STATUS_ACTIVE)
        self.assertEqual(subscription.provider, Subscription.PROVIDER_ADYEN)

        self.subscription.refresh_from_db()
        self.assertEqual(self.subscription.status, Subscription.STATUS_EXPIRED)
        self.assertEqual(self.subscription.paid_until, timezone.now().date())
        self.assertEqual(self.user.tier, self.plan.tier)

        mocked_segment.assert_called_once_with(
            subscription,
            self.current_plan,
            web_user_agent,
            '127.0.0.1',
            self.country.code,
        )

    @responses.activate
    def test_create_subscription_error_keeps_current_tier(self):
        self._add_country_check_response(self.country.code)
        self._add_checkout_response('Refused')
        response = self.client.post(self.url)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data['is_success'], False)
        subscription = self.user.current_subscription()
        payment = subscription.latest_payment()

        self.subscription.refresh_from_db()
        self.assertEqual(subscription, self.subscription)
        self.assertEqual(payment, self.transaction)
        self.assertEqual(self.subscription.status, Subscription.STATUS_ACTIVE)

        failed_subscriptions = self.user.subscriptions.filter(plan=self.plan)
        self.assertEqual(failed_subscriptions.count(), 1)
        failed_subscription = failed_subscriptions.first()
        failed_payment = failed_subscription.latest_payment(allow_failed=True)

        self.assertEqual(failed_subscription.status, Subscription.STATUS_ERROR)
        self.assertEqual(failed_payment.status, PaymentTransaction.STATUS_DECLINED)
        self.assertEqual(self.user.tier, self.current_plan.tier)
