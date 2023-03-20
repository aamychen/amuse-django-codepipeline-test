from datetime import date, timedelta
from decimal import Decimal
from math import floor
from unittest import mock
from unittest.mock import patch

import pytest
import responses
from dateutil.relativedelta import relativedelta
from django.conf import settings
from django.test import TestCase
from django.utils import timezone
from flaky import flaky
from freezegun import freeze_time

from amuse.tests.helpers import add_zendesk_mock_post_response
from amuse.tests.test_vendor.test_adyen.base import AdyenBaseTestCase
from amuse.vendor.apple.exceptions import UnknownAppleError
from countries.tests.factories import CountryFactory, CurrencyFactory
from payments.models import PaymentTransaction
from payments.tests.factories import PaymentTransactionFactory
from subscriptions.helpers import (
    expire_subscriptions,
    renew_adyen_subscriptions,
    renew_apple_subscriptions,
    calculate_tier_upgrade_price,
)
from subscriptions.models import Subscription
from subscriptions.tests.factories import (
    SubscriptionFactory,
    SubscriptionPlanFactory,
    PriceCardFactory,
    IntroductoryPriceCardFactory,
)
from subscriptions.tests.helpers import apple_receipt_validation_response
from users.tests.factories import UserFactory, UserMetadataFactory

LATEST_RECEIPT = 'MIKKXQYJKoZIhvcNAQcCoIKKTjCCikoCAQExCzAJBgUrDgMCGgUAMIJ5/gYJKoZIhvcNA'


class RenewAdyenSubscriptionsBaseTestCase:
    @responses.activate
    @mock.patch('subscriptions.helpers.logger.info')
    @mock.patch('subscriptions.helpers.subscription_successful_renewal')
    def test_successful_renew_extends_paid_until_by_plan_period(
        self, mock_analytics, mock_logger
    ):
        self._add_checkout_response('Authorised')
        expected_paid_until = timezone.now().date() + relativedelta(months=1)
        first_payment = self.subscription.latest_payment()

        renew_adyen_subscriptions(is_dry_run=False)
        self.subscription.refresh_from_db()

        mock_logger.assert_has_calls(
            (
                mock.call("Renewing subscription with id %s" % self.subscription.pk),
                mock.call("Renewed 1 subscriptions"),
            )
        )
        mock_analytics.assert_called_once()

        self.assertEqual(self.subscription.paid_until, expected_paid_until)
        self.assertEqual(
            self.subscription.latest_payment().category,
            PaymentTransaction.CATEGORY_RENEWAL,
        )

        # Renewing again will not extend since paid_until is not passed
        renew_adyen_subscriptions(is_dry_run=False)
        self.assertEqual(self.subscription.paid_until, expected_paid_until)
        self.assertEqual(self.subscription.status, Subscription.STATUS_ACTIVE)

        # Assert PriceCard values are used in PaymentTransaction
        renewal_transaction = self.subscription.latest_payment()
        price_card = self.subscription.plan.get_price_card()
        country = renewal_transaction.country
        self.assertEqual(price_card.price, renewal_transaction.amount)
        self.assertEqual(
            country.vat_amount(price_card.price), renewal_transaction.vat_amount
        )
        self.assertEqual(first_payment.amount, renewal_transaction.amount)

    @mock.patch('subscriptions.helpers.renew_subscription')
    def test_does_not_renew_expired_subscription(self, mock_renewal):
        self.subscription.status = Subscription.STATUS_EXPIRED
        self.subscription.valid_until = self.subscription.created + timedelta(days=10)
        self.subscription.save()

        renew_adyen_subscriptions(is_dry_run=False)

        self.assertEqual(mock_renewal.call_count, 0)

    @mock.patch('subscriptions.helpers.renew_subscription')
    def test_dry_run_does_not_change_db(self, mock_renewal):
        renew_adyen_subscriptions(True)

        self.assertEqual(mock_renewal.call_count, 0)

    @responses.activate
    @mock.patch('subscriptions.helpers.renew_subscription')
    @mock.patch('subscriptions.helpers.logger.info')
    def test_does_not_renew_ios_subscription(self, mock_logger, mock_renewal):
        add_zendesk_mock_post_response()
        ios_user = UserFactory()
        ios_subscription = SubscriptionFactory(
            user=ios_user,
            plan=self.plan,
            valid_from=self.purchased_at,
            provider=Subscription.PROVIDER_IOS,
        )
        ios_payment = PaymentTransactionFactory(
            subscription=ios_subscription, user=ios_user
        )
        ios_payment.created = timezone.now() - relativedelta(months=1)
        ios_payment.save()

        renew_adyen_subscriptions(is_dry_run=False)

        mock_logger.assert_has_calls(
            (
                mock.call("Renewing subscription with id %s" % self.subscription.pk),
                mock.call("Renewed 1 subscriptions"),
            )
        )
        self.assertEqual(mock_renewal.call_count, 1)

    @responses.activate
    @flaky(max_runs=3)
    @mock.patch('subscriptions.helpers.renew_subscription')
    @mock.patch('subscriptions.helpers.logger.info')
    def test_does_not_renew_free_subscription(self, mock_logger, mock_renewal):
        add_zendesk_mock_post_response()
        free_subscription = SubscriptionFactory()

        renew_adyen_subscriptions(is_dry_run=False)

        mock_logger.assert_has_calls(
            (
                mock.call("Renewing subscription with id %s" % self.subscription.pk),
                mock.call(
                    'Skipping and setting to ERROR subscription with id %s because it has no Adyen payments'
                    % free_subscription.pk
                ),
                mock.call("Renewed 1 subscriptions"),
            )
        )
        self.assertEqual(mock_renewal.call_count, 1)
        free_subscription.refresh_from_db()
        self.assertEqual(free_subscription.status, Subscription.STATUS_ERROR)

    @responses.activate
    @mock.patch(
        'subscriptions.helpers.renew_subscription',
        return_value={'is_success': False, 'error_message': 'error'},
    )
    @mock.patch('subscriptions.helpers.logger.info')
    def test_adyen_error_handled(self, mock_logger, mock_renewal):
        add_zendesk_mock_post_response()

        renew_adyen_subscriptions(is_dry_run=False)

        mock_logger.assert_has_calls(
            (
                mock.call(
                    "Error renewing subscription with id %s: error"
                    % self.subscription.pk
                ),
                mock.call("Renewed 0 subscriptions. Error renewing 1 subscriptions"),
            )
        )
        self.assertEqual(mock_renewal.call_count, 1)
        self.assertEqual(
            self.subscription.latest_payment().category,
            PaymentTransaction.CATEGORY_RETRY,
        )


class RenewAdyenSubscriptionsTestCase(
    AdyenBaseTestCase, RenewAdyenSubscriptionsBaseTestCase
):
    @responses.activate
    def setUp(self):
        super().setUp()
        add_zendesk_mock_post_response()
        now = timezone.now()
        today = now.date()
        self.purchased_at = today - relativedelta(months=1, days=1)
        self.user = UserFactory()
        self.plan = SubscriptionPlanFactory(period=1, grace_period_days=0, trial_days=0)
        self.subscription = SubscriptionFactory(
            plan=self.plan, valid_from=self.purchased_at, user=self.user
        )
        self.amount = self.subscription.plan.get_price_card().price
        self.payment = PaymentTransactionFactory(
            user=self.user, subscription=self.subscription, amount=self.amount
        )
        self.payment.created = now - relativedelta(months=1, days=1)
        self.payment.paid_until = now
        self.payment.save()


class RenewGracePeriodAdyenSubscriptionsTestCase(
    AdyenBaseTestCase, RenewAdyenSubscriptionsBaseTestCase
):
    @responses.activate
    def setUp(self):
        super().setUp()
        add_zendesk_mock_post_response()
        now = timezone.now()
        today = now.date()
        self.purchased_at = today - relativedelta(months=1, days=1)
        self.user = UserFactory()
        self.plan = SubscriptionPlanFactory(period=1, grace_period_days=7, trial_days=0)
        self.subscription = SubscriptionFactory(
            plan=self.plan,
            valid_from=self.purchased_at,
            user=self.user,
            status=Subscription.STATUS_GRACE_PERIOD,
            valid_until=today + timedelta(days=self.plan.grace_period_days),
        )
        self.amount = self.subscription.plan.get_price_card().price
        self.payment = PaymentTransactionFactory(
            user=self.user,
            subscription=self.subscription,
            paid_until=now,
            amount=self.amount,
        )
        self.payment.created = timezone.now() - relativedelta(months=1, days=1)
        self.payment.save()

    @responses.activate
    @mock.patch('subscriptions.helpers.logger.info')
    def test_payment_failed_on_last_grace_period_day_sets_expired(self, mock_logger):
        self._add_checkout_response('Refused')
        self.plan.grace_period_days = 0
        self.plan.save()
        self.subscription.valid_until = timezone.now().date()
        self.subscription.save()

        renew_adyen_subscriptions(is_dry_run=False)
        self.subscription.refresh_from_db()

        mock_logger.assert_has_calls(
            (
                mock.call(
                    'Error renewing subscription with id %s: Payment failed'
                    % self.subscription.pk
                ),
                mock.call('Renewed 0 subscriptions. Error renewing 1 subscriptions'),
            )
        )
        self.assertEqual(self.subscription.status, Subscription.STATUS_EXPIRED)
        self.assertEqual(
            self.subscription.latest_payment(allow_failed=True).category,
            PaymentTransaction.CATEGORY_RENEWAL,
        )


class RenewalMultipleFailureTestCase(AdyenBaseTestCase):
    @mock.patch('amuse.tasks.zendesk_create_or_update_user')
    def setUp(self, mock_zendesk):
        self.valid_from = date(2020, 3, 12)
        self.subscription = SubscriptionFactory(
            plan__period=12,
            plan__trial_days=14,
            plan__grace_period_days=14,
            valid_from=self.valid_from,
        )
        self.user = self.subscription.user
        self.auth_transaction = PaymentTransactionFactory(
            subscription=self.subscription,
            paid_until=date(2020, 4, 11),
            user=self.user,
            type=PaymentTransaction.TYPE_AUTHORISATION,
        )

    @responses.activate
    def test_renewal_renews_subscriptions_correctly_over_time(self):
        with freeze_time('2020-04-11'):
            self._add_checkout_response('Refused')
            renew_adyen_subscriptions(is_dry_run=False)
            expire_subscriptions()

        self.subscription.refresh_from_db()
        self.assertEqual(self.subscription.status, Subscription.STATUS_GRACE_PERIOD)

        with freeze_time('2020-04-12'):
            self._add_checkout_response('Refused')
            renew_adyen_subscriptions(is_dry_run=False)
            expire_subscriptions()

        self.subscription.refresh_from_db()
        self.assertEqual(self.subscription.status, Subscription.STATUS_EXPIRED)

        with freeze_time('2020-04-25'):
            self._add_checkout_response('Refused')
            renew_adyen_subscriptions(is_dry_run=False)
            expire_subscriptions()

        self.subscription.refresh_from_db()
        self.assertEqual(self.subscription.status, Subscription.STATUS_EXPIRED)


class RenewAppleSubscriptionsTestCase(TestCase):
    @mock.patch('amuse.tasks.zendesk_create_or_update_user')
    def setUp(self, mock_zendesk):
        trial_until = timezone.now() - timedelta(days=1)
        self.original_transaction_id = '123'
        self.first_payment = PaymentTransactionFactory(
            customer_payment_payload={'receipt_data': '...'},
            subscription__plan__trial_days=30,
            subscription__provider=Subscription.PROVIDER_IOS,
            subscription__status=Subscription.STATUS_GRACE_PERIOD,
            subscription__valid_until=trial_until.date(),
            subscription__grace_period_until=trial_until.date() + timedelta(days=14),
            payment_method__external_recurring_id=self.original_transaction_id,
            payment_method__method='AAPL',
            external_transaction_id=self.original_transaction_id,
            paid_until=trial_until,
        )
        self.subscription = self.first_payment.subscription
        UserMetadataFactory(
            user=self.subscription.user, pro_trial_expiration_date=trial_until.date()
        )
        self.expires_at = timezone.now() + timedelta(days=29)
        self.payload = apple_receipt_validation_response(
            auto_renew_status='1',
            expires_date=self.expires_at,
            external_recurring_id=self.original_transaction_id,
            product_id=self.subscription.plan.apple_product_id,
        )

    @responses.activate
    def test_success_adds_transaction_and_extends_paid_until(self):
        responses.add(
            responses.POST, settings.APPLE_VALIDATION_URL, json=self.payload, status=200
        )

        renew_apple_subscriptions(is_dry_run=False)
        self.subscription.refresh_from_db()

        self.assertEqual(PaymentTransaction.objects.count(), 2)
        self.assertEqual(self.subscription.paid_until, self.expires_at.date())
        self.assertEqual(self.subscription.status, Subscription.STATUS_ACTIVE)
        self.assertIsNone(self.subscription.valid_until)
        self.assertIsNone(self.subscription.grace_period_until)
        self.assertEqual(
            self.subscription.latest_payment().category,
            PaymentTransaction.CATEGORY_RENEWAL,
        )
        self.assertEqual(
            self.subscription.latest_payment().platform,
            PaymentTransaction.PLATFORM_CRON,
        )

    @mock.patch(
        'subscriptions.helpers.AppleReceiptValidationAPIClient.validate_receipt',
        side_effect=UnknownAppleError,
    )
    @mock.patch('subscriptions.helpers.logger.info')
    def test_unknown_apple_error_skips_subscription_and_logs(
        self, mock_logger, mock_apple_client
    ):
        renew_apple_subscriptions(is_dry_run=False)
        self.subscription.refresh_from_db()

        self.assertEqual(PaymentTransaction.objects.count(), 1)
        mock_logger.assert_called_with(
            'Renewed 0 Apple subscriptions. Error renewing 1 subscriptions'
        )

    @responses.activate
    @mock.patch('subscriptions.helpers.subscription_successful_renewal')
    def test_no_new_transaction_considered_failure_does_not_send_segment_event(
        self, mock_segment
    ):
        self.payload['latest_receipt_info'] = self.payload['latest_receipt_info'][:1]
        self.payload['latest_receipt_info'][0][
            'transaction_id'
        ] = self.original_transaction_id
        responses.add(
            responses.POST, settings.APPLE_VALIDATION_URL, json=self.payload, status=200
        )

        renew_apple_subscriptions(is_dry_run=False)
        self.subscription.refresh_from_db()

        self.assertEqual(PaymentTransaction.objects.count(), 1)
        mock_segment.assert_not_called()

    @responses.activate
    def test_renew_with_plan_change(self):
        new_plan = SubscriptionPlanFactory(apple_product_id='new_plan_id')
        new_payload = self.payload = apple_receipt_validation_response(
            auto_renew_status='1',
            expires_date=self.expires_at,
            external_recurring_id=self.original_transaction_id,
            product_id=new_plan.apple_product_id,
        )
        responses.add(
            responses.POST, settings.APPLE_VALIDATION_URL, json=new_payload, status=200
        )
        renew_apple_subscriptions(is_dry_run=False)
        self.subscription.refresh_from_db()

        self.assertEqual(self.subscription.plan, new_plan)
        self.assertEqual(PaymentTransaction.objects.count(), 2)
        self.assertEqual(self.subscription.paid_until, self.expires_at.date())
        self.assertEqual(self.subscription.status, Subscription.STATUS_ACTIVE)
        self.assertIsNone(self.subscription.valid_until)
        self.assertIsNone(self.subscription.grace_period_until)
        self.assertEqual(
            self.subscription.latest_payment().category,
            PaymentTransaction.CATEGORY_RENEWAL,
        )
        self.assertEqual(
            self.subscription.latest_payment().platform,
            PaymentTransaction.PLATFORM_CRON,
        )


class ExpireSubscriptionsTestCase(AdyenBaseTestCase):
    @responses.activate
    def setUp(self):
        add_zendesk_mock_post_response()
        now = timezone.now()
        self.today = now.date()
        self.subscription = SubscriptionFactory(
            plan__grace_period_days=14, valid_until=self.today
        )
        self.ios_subscription = SubscriptionFactory(
            plan__grace_period_days=14,
            plan__trial_days=0,
            provider=Subscription.PROVIDER_IOS,
            valid_until=self.today,
        )
        self.vip_subscription = SubscriptionFactory(
            provider=Subscription.PROVIDER_VIP, valid_until=self.today
        )
        PaymentTransactionFactory(paid_until=now, subscription=self.ios_subscription)

    @flaky(max_runs=3)
    @mock.patch('subscriptions.helpers.logger.info')
    def test_valid_until_passed_sets_status_expired(self, mock_logger):
        self.subscription.valid_until -= timedelta(days=1)
        self.subscription.save()
        self.ios_subscription.valid_until -= timedelta(days=1)
        self.ios_subscription.save()
        self.vip_subscription.valid_until -= timedelta(days=1)
        self.vip_subscription.save()

        expire_subscriptions()
        self.subscription.refresh_from_db()
        self.ios_subscription.refresh_from_db()
        self.vip_subscription.refresh_from_db()

        mock_logger.assert_has_calls(
            [
                mock.call('Expired 1 Adyen subscriptions'),
                mock.call('Expired 0 Apple subscriptions'),
                mock.call('Expired 1 VIP subscriptions'),
            ]
        )
        mock_logger.reset_mock()
        self.assertEqual(self.subscription.status, Subscription.STATUS_EXPIRED)
        self.assertEqual(self.ios_subscription.status, Subscription.STATUS_GRACE_PERIOD)
        self.assertEqual(self.vip_subscription.status, Subscription.STATUS_EXPIRED)
        self.assertEqual(
            self.ios_subscription.grace_period_until,
            self.ios_subscription.allowed_grace_period_until(),
        )

        # Running command after Apple subscription grace period is ended sets EXPIRED
        with freeze_time(self.ios_subscription.grace_period_until + timedelta(days=1)):
            expire_subscriptions()

        self.subscription.refresh_from_db()
        self.ios_subscription.refresh_from_db()
        self.vip_subscription.refresh_from_db()

        mock_logger.assert_has_calls(
            [
                mock.call('Expired 0 Adyen subscriptions'),
                mock.call('Expired 1 Apple subscriptions'),
                mock.call('Expired 0 VIP subscriptions'),
            ]
        )
        self.assertEqual(self.subscription.status, Subscription.STATUS_EXPIRED)
        self.assertEqual(self.ios_subscription.status, Subscription.STATUS_EXPIRED)
        self.assertEqual(self.vip_subscription.status, Subscription.STATUS_EXPIRED)

    @mock.patch('subscriptions.helpers.logger.info')
    def test_still_valid_does_not_set_status_expired(self, mock_logger):
        expire_subscriptions()
        self.subscription.refresh_from_db()

        mock_logger.assert_has_calls(
            [
                mock.call('Expired 0 Adyen subscriptions'),
                mock.call('Expired 0 Apple subscriptions'),
                mock.call('Expired 0 VIP subscriptions'),
            ]
        )
        self.assertEqual(self.subscription.status, Subscription.STATUS_ACTIVE)

        self.vip_subscription.valid_until = None
        self.vip_subscription.save()

        expire_subscriptions()
        self.vip_subscription.refresh_from_db()

        mock_logger.assert_has_calls(
            [
                mock.call('Expired 0 Adyen subscriptions'),
                mock.call('Expired 0 Apple subscriptions'),
                mock.call('Expired 0 VIP subscriptions'),
            ]
        )
        self.assertEqual(self.vip_subscription.status, Subscription.STATUS_ACTIVE)

    @mock.patch('subscriptions.helpers.logger.info')
    def test_apple_subscription_valid_until_is_unset_has_trial(self, mock_logger):
        self.ios_subscription.valid_until = None
        self.ios_subscription.save()
        self.ios_subscription.plan.trial_days = 30
        self.ios_subscription.plan.save()

        expire_subscriptions()
        self.subscription.refresh_from_db()

        mock_logger.assert_has_calls(
            [
                mock.call('Expired 0 Adyen subscriptions'),
                mock.call('Expired 0 Apple subscriptions'),
                mock.call('Expired 0 VIP subscriptions'),
            ]
        )
        self.assertEqual(self.subscription.status, Subscription.STATUS_ACTIVE)


@pytest.mark.parametrize(
    'payload',
    [
        {
            'latest_receipt': LATEST_RECEIPT,
            'password': 'password',
            'notification_type': 'Does Not Exist',
        },
        {
            'unified_receipt': {'latest_receipt': LATEST_RECEIPT},
            'password': 'password',
            'notification_type': 'Does Not Exist',
        },
    ],
)
class RenewAppleSubscriptionsPriceCardTestCase(TestCase):
    @mock.patch('amuse.tasks.zendesk_create_or_update_user')
    def setUp(self, mock_zendesk):
        trial_until = timezone.now() - timedelta(days=1)
        self.original_transaction_id = '123'
        self.first_payment = PaymentTransactionFactory(
            customer_payment_payload={'receipt_data': '...'},
            subscription__plan__trial_days=30,
            subscription__provider=Subscription.PROVIDER_IOS,
            subscription__status=Subscription.STATUS_GRACE_PERIOD,
            subscription__valid_until=trial_until.date(),
            subscription__grace_period_until=trial_until.date() + timedelta(days=14),
            payment_method__external_recurring_id=self.original_transaction_id,
            payment_method__method='AAPL',
            external_transaction_id=self.original_transaction_id,
            paid_until=trial_until,
        )
        self.subscription = self.first_payment.subscription
        self.country = self.first_payment.country
        self.subscription_plan = self.first_payment.plan
        self.price_card = self.subscription_plan.get_price_card(self.country.code)

        self.first_payment.amount = self.price_card.price

        UserMetadataFactory(
            user=self.subscription.user, pro_trial_expiration_date=trial_until.date()
        )
        self.expires_at = timezone.now() + timedelta(days=29)
        self.payload = apple_receipt_validation_response(
            auto_renew_status='1',
            expires_date=self.expires_at,
            external_recurring_id=self.original_transaction_id,
            product_id=self.subscription.plan.apple_product_id,
        )

    @responses.activate
    def test_success_adds_transaction_and_extends_paid_until(self):
        responses.add(
            responses.POST, settings.APPLE_VALIDATION_URL, json=self.payload, status=200
        )
        renew_apple_subscriptions(is_dry_run=False)
        self.subscription.refresh_from_db()

        self.assertEqual(PaymentTransaction.objects.count(), 2)
        self.assertEqual(self.subscription.paid_until, self.expires_at.date())
        self.assertEqual(self.subscription.status, Subscription.STATUS_ACTIVE)
        self.assertIsNone(self.subscription.valid_until)
        self.assertIsNone(self.subscription.grace_period_until)
        self.assertEqual(
            self.subscription.latest_payment().category,
            PaymentTransaction.CATEGORY_RENEWAL,
        )
        # Assert PriceCard values are used
        renewal_transaction = PaymentTransaction.objects.last()
        self.assertEqual(self.price_card.price, renewal_transaction.amount)
        self.assertEqual(
            self.country.vat_amount(self.subscription_plan.get_price_card().price),
            renewal_transaction.vat_amount,
        )
        self.assertEquals(self.first_payment.country, renewal_transaction.country)
        self.assertEquals(self.first_payment.amount, renewal_transaction.amount)


class CalculateTierUpgradePriceTestCase(TestCase):
    @responses.activate
    @patch('amuse.tasks.zendesk_create_or_update_user')
    def setUp(self, _):
        self.price = Decimal('100.0')
        self.user = UserFactory()
        self.country = CountryFactory(is_adyen_enabled=True)
        self.currency = CurrencyFactory()

        self.plan = SubscriptionPlanFactory(period=1, create_card=False)

        self.old_plan = SubscriptionPlanFactory(period=1, create_card=False)

        PriceCardFactory(
            plan=self.plan,
            price=self.price,
            currency=self.currency,
            countries=[self.country],
        )
        PriceCardFactory(
            plan=self.old_plan,
            price=self.price,
            currency=self.currency,
            countries=[self.country],
        )

    @responses.activate
    @patch('amuse.tasks.zendesk_create_or_update_user')
    def test_missing_payment_raises_value_error(self, _):
        subscription = SubscriptionFactory(user=self.user)

        with self.assertRaises(ValueError) as err:
            calculate_tier_upgrade_price(subscription, self.plan)

        self.assertEqual(
            str(err.exception),
            f'No valid payments found for Subscription {subscription.pk}, unable to calculate Tier upgrade price',
        )

    @responses.activate
    @patch('amuse.tasks.zendesk_create_or_update_user')
    def test_grace_period_gets_full_price(self, _):
        subscription = SubscriptionFactory(
            user=self.user, status=Subscription.STATUS_GRACE_PERIOD, plan=self.old_plan
        )
        transaction = PaymentTransactionFactory(
            subscription=subscription,
            user=self.user,
            paid_until=timezone.now() - timezone.timedelta(days=5),
            country=self.country,
            plan=self.old_plan,
            currency=self.currency,
        )
        full_price = self.plan.pricecard_set.get(currency=self.currency).price

        price, currency = calculate_tier_upgrade_price(subscription, self.plan)
        self.assertEqual(price, full_price)
        self.assertEqual(currency, transaction.currency)

    @responses.activate
    @patch('amuse.tasks.zendesk_create_or_update_user')
    def test_active_subscription_gets_discounted_price(self, _):
        subscription = SubscriptionFactory(user=self.user, plan=self.old_plan)
        paid_until = timezone.now() + timezone.timedelta(days=15)
        paid_from = paid_until - relativedelta(months=1)
        transaction = PaymentTransactionFactory(
            subscription=subscription,
            user=self.user,
            paid_until=paid_until,
            country=self.country,
            plan=self.old_plan,
            currency=self.currency,
            amount=self.price,
        )
        transaction.created = paid_from
        transaction.save()
        total_days = (paid_until - paid_from).days
        full_price = self.plan.pricecard_set.get(currency=self.currency).price
        old_price = self.price
        price_to_discount = (old_price / total_days) * 15
        final_price = max(0, floor(full_price - price_to_discount) - 1) + Decimal(
            '0.99'
        )

        price, currency = calculate_tier_upgrade_price(subscription, self.plan)
        self.assertEqual(price, Decimal(final_price))
        self.assertEqual(currency, transaction.currency)

    @responses.activate
    @patch('amuse.tasks.zendesk_create_or_update_user')
    def test_active_intro_subscription_gets_discounted_price(self, _):
        intro_price = Decimal('20.0')
        introductory_card = IntroductoryPriceCardFactory(
            plan=self.plan,
            countries=[self.country],
            currency=self.currency,
            price=intro_price,
        )

        subscription = SubscriptionFactory(user=self.user, plan=self.old_plan)
        paid_until = timezone.now() + timezone.timedelta(days=15)
        paid_from = paid_until - relativedelta(months=1)
        transaction = PaymentTransactionFactory(
            subscription=subscription,
            user=self.user,
            paid_until=paid_until,
            country=self.country,
            plan=self.old_plan,
            currency=self.currency,
            amount=intro_price,
        )
        transaction.created = paid_from
        transaction.save()
        total_days = (paid_until - paid_from).days
        full_price = self.plan.pricecard_set.get(currency=self.currency).price
        old_price = intro_price
        price_to_discount = (old_price / total_days) * 15
        final_price = max(0, floor(full_price - price_to_discount) - 1) + Decimal(
            '0.99'
        )

        price, currency = calculate_tier_upgrade_price(subscription, self.plan)
        self.assertEqual(price, Decimal(final_price))
        self.assertEqual(currency, transaction.currency)

    @flaky(max_runs=3)
    @responses.activate
    @patch('amuse.tasks.zendesk_create_or_update_user')
    def test_first_day_of_subscription_gets_full_discount(self, _):
        now = timezone.now()
        subscription = SubscriptionFactory(user=self.user, plan=self.old_plan)
        paid_until = now + relativedelta(months=1)
        transaction = PaymentTransactionFactory(
            subscription=subscription,
            user=self.user,
            paid_until=paid_until,
            country=self.country,
            plan=self.old_plan,
            currency=self.currency,
        )
        transaction.created = now
        transaction.save()
        full_price = self.plan.pricecard_set.get(currency=self.currency).price
        old_price = self.old_plan.pricecard_set.get(currency=self.currency).price
        final_price = floor(full_price - old_price) + Decimal('0.99')

        price, currency = calculate_tier_upgrade_price(subscription, self.plan)
        self.assertEqual(price, Decimal(final_price))
        self.assertEqual(currency, transaction.currency)

    @responses.activate
    @patch('amuse.tasks.zendesk_create_or_update_user')
    def test_multiple_price_cards_filters_by_country(self, _):
        subscription = SubscriptionFactory(
            user=self.user, plan=self.old_plan, status=Subscription.STATUS_GRACE_PERIOD
        )
        price_card = PriceCardFactory(
            plan=self.old_plan, countries=[self.country], currency=self.currency
        )
        transaction = PaymentTransactionFactory(
            subscription=subscription,
            user=self.user,
            paid_until=timezone.now() - timezone.timedelta(days=5),
            country=self.country,
            plan=self.old_plan,
            currency=self.currency,
        )
        full_price = self.plan.pricecard_set.get(
            currency=self.currency, countries=self.country
        ).price
        price, currency = calculate_tier_upgrade_price(subscription, self.plan)
        self.assertNotEqual(price, price_card.price)
        self.assertEqual(price, full_price)
