from datetime import timedelta, date
from unittest.mock import patch

import responses
from dateutil.relativedelta import relativedelta
from django.utils import timezone

from amuse.tests.helpers import add_zendesk_mock_post_response
from amuse.tests.test_vendor.test_adyen.base import AdyenBaseTestCase
from amuse.vendor.adyen import renew_subscription, AdyenSubscription
from countries.models import Currency
from countries.tests.factories import CurrencyFactory, CountryFactory
from payments.models import PaymentTransaction, PaymentMethod
from payments.tests.factories import PaymentTransactionFactory
from subscriptions.models import Subscription, PriceCard, SubscriptionPlanChanges
from subscriptions.tests.factories import (
    SubscriptionFactory,
    SubscriptionPlanFactory,
    PriceCardFactory,
)
from amuse.settings.constants import NONLOCALIZED_PAYMENTS_COUNTRY


class AdyenRenewSubscriptionTestCase(AdyenBaseTestCase):
    @responses.activate
    def setUp(self):
        add_zendesk_mock_post_response()
        self.plan = SubscriptionPlanFactory(trial_days=0, period=1, grace_period_days=7)
        self.subscription = SubscriptionFactory(
            status=Subscription.STATUS_ACTIVE, plan=self.plan
        )
        self.payment_method = self.subscription.payment_method
        self.user = self.subscription.user
        self.payment = PaymentTransactionFactory(
            subscription=self.subscription,
            user=self.user,
            paid_until=timezone.now() + timedelta(1),
            payment_method=self.payment_method,
        )

    def _assert_renewal_added_transaction(self, subscription_active):
        self.subscription.refresh_from_db()

        self.assertEqual(Subscription.objects.count(), 1)
        self.assertEqual(self.subscription.paymenttransaction_set.count(), 2)
        if subscription_active:
            self.assertIsNone(self.subscription.valid_until)
            self.assertEqual(self.subscription.status, Subscription.STATUS_ACTIVE)
        else:
            payment = PaymentTransaction.objects.first()
            valid_until = payment.subscription.allowed_grace_period_until()
            self.assertEqual(
                self.subscription.valid_until, self.subscription.paid_until
            )
            self.assertEqual(self.subscription.status, Subscription.STATUS_GRACE_PERIOD)
            self.assertEqual(self.subscription.grace_period_until, valid_until)

    @responses.activate
    def test_payment_success(self):
        self._add_checkout_response('Authorised', is_renewal=True)
        self.assertIsNone(self.subscription.valid_until)

        response = renew_subscription(self.subscription)

        self.assertTrue(response['is_success'])
        self._assert_renewal_added_transaction(subscription_active=True)
        self._assert_payment_and_subscription(
            payment_status=PaymentTransaction.STATUS_APPROVED,
            subscription_user_id=self.user.pk,
            subscription_status=Subscription.STATUS_ACTIVE,
            is_renewal=True,
        )

    @responses.activate
    def test_payment_success_with_plan_change(self):
        new_plan = plan = SubscriptionPlanFactory(
            trial_days=0, period=1, grace_period_days=0
        )

        SubscriptionPlanChanges.objects.create(
            subscription=self.subscription,
            current_plan=self.subscription.plan,
            new_plan=new_plan,
        )

        self._add_checkout_response('Authorised', is_renewal=True)
        self.assertIsNone(self.subscription.valid_until)

        response = renew_subscription(self.subscription)

        self.assertTrue(response['is_success'])
        self._assert_renewal_added_transaction(subscription_active=True)
        sub = Subscription.objects.get(id=self.subscription.id)
        tx = PaymentTransaction.objects.filter(subscription=sub).last()
        self.assertEqual(sub.plan, new_plan)
        self.assertEqual(tx.plan, new_plan)

    @responses.activate
    def test_payment_success_sets_renew_category(self):
        self._add_checkout_response('Authorised', is_renewal=True)
        self.assertIsNone(self.subscription.valid_until)

        response = renew_subscription(self.subscription)

        self.assertTrue(response['is_success'])
        self._assert_renewal_added_transaction(subscription_active=True)
        sub = Subscription.objects.get(id=self.subscription.id)
        tx = PaymentTransaction.objects.filter(subscription=sub).last()
        self.assertEqual(tx.category, PaymentTransaction.CATEGORY_RENEWAL)

    @responses.activate
    def test_missing_price_card_data_uses_default_USD_currency(self):
        # for special case Plans (ex. the Pro Yearly Campaign) we don't have PriceCard
        # data for all currencies, so we use USD as the default one
        plan = SubscriptionPlanFactory(trial_days=0, period=1, grace_period_days=7)
        price_card = plan.pricecard_set.first()
        self.assertEqual(plan.pricecard_set.count(), 1)
        self.subscription.plan = plan
        assert self.subscription.payment_method is not None
        self.subscription.save()

        self.assertNotEqual(self.payment.currency.code, 'USD')

        self._add_checkout_response('Authorised', is_renewal=True)
        self.assertIsNone(self.subscription.valid_until)
        self.assertNotEqual(self.payment.currency, price_card.currency)

        response = renew_subscription(self.subscription)

        self.assertTrue(response['is_success'], response)
        self._assert_renewal_added_transaction(subscription_active=True)
        payment = PaymentTransaction.objects.last()
        self.assertEqual(
            payment.external_transaction_id, self.mock_response["pspReference"]
        )
        self.assertEqual(payment.subscription.plan_id, plan.pk)
        self.assertEqual(payment.status, PaymentTransaction.STATUS_APPROVED)
        self.assertEqual(payment.subscription.user_id, self.user.pk)
        self.assertEqual(payment.subscription.status, Subscription.STATUS_ACTIVE)
        self.assertEqual(payment.vat_percentage, payment.country.vat_percentage)
        self.assertEqual(payment.amount, price_card.price)
        self.assertEqual(payment.currency, price_card.currency)

    @responses.activate
    def test_payment_success_doesnt_create_new_payment_method(self):
        self._add_checkout_response('Authorised', is_renewal=True)
        month, year = self.mock_response['additionalData']['expiryDate'].split('/')
        expiry_date = date(int(year), int(month), 1) + relativedelta(months=1, days=-1)
        self.payment_method.expiry_date = expiry_date
        self.payment_method.summary = self.mock_response['additionalData'][
            'cardSummary'
        ]
        self.payment_method.method = self.mock_response['additionalData'][
            'paymentMethod'
        ]
        self.payment_method.external_recurring_id = '123456789'
        self.payment_method.save()

        self.assertIsNone(self.subscription.valid_until)

        response = renew_subscription(self.subscription)

        self.assertTrue(response['is_success'])
        self._assert_renewal_added_transaction(subscription_active=True)
        self._assert_payment_and_subscription(
            payment_status=PaymentTransaction.STATUS_APPROVED,
            subscription_user_id=self.user.pk,
            subscription_status=Subscription.STATUS_ACTIVE,
            is_renewal=True,
        )

        payment_methods = PaymentMethod.objects.filter(user=self.user)
        self.assertEqual(payment_methods.count(), 1)

    @responses.activate
    def test_payment_pending(self):
        self._add_checkout_response('Pending', is_renewal=True)
        self.assertIsNone(self.subscription.valid_until)

        response = renew_subscription(self.subscription)

        self.assertFalse(response['is_success'])
        self._assert_renewal_added_transaction(subscription_active=False)
        payment = PaymentTransaction.objects.last()
        # pending payments have no external transaction ID
        self.assertEqual(payment.external_transaction_id, '')
        self.assertEqual(payment.status, PaymentTransaction.STATUS_PENDING)
        self.assertEqual(payment.subscription.user_id, self.user.pk)
        self.assertEqual(payment.subscription.status, Subscription.STATUS_GRACE_PERIOD)

    @responses.activate
    def test_payment_refused(self):
        self._add_checkout_response('Refused', is_renewal=True)
        self.assertIsNone(self.subscription.valid_until)

        response = renew_subscription(self.subscription)

        self.assertFalse(response['is_success'])
        self._assert_renewal_added_transaction(subscription_active=False)
        self._assert_payment_and_subscription(
            payment_status=PaymentTransaction.STATUS_DECLINED,
            subscription_user_id=self.user.pk,
            subscription_status=Subscription.STATUS_GRACE_PERIOD,
        )

    @responses.activate
    @patch.object(AdyenSubscription, 'renew')
    @patch('amuse.vendor.adyen.logger')
    def test_uncaught_error_is_logged_and_continued(self, mock_logger, mock_renew):
        error_msg = 'Something broke!'

        def side_effect(*args, **kwargs):
            raise ValueError(error_msg)

        mock_renew.side_effect = side_effect
        self.assertIsNone(self.subscription.valid_until)

        response = renew_subscription(self.subscription)

        self.assertFalse(response['is_success'])
        self.payment.refresh_from_db()
        self.subscription.refresh_from_db()
        self.assertEqual(self.payment.status, PaymentTransaction.STATUS_APPROVED)
        self.assertEqual(self.subscription.status, Subscription.STATUS_GRACE_PERIOD)
        mock_logger.error.assert_called_with(
            f'Uncaught exception occurred while renewing Subscription {self.subscription.pk}: {error_msg}',
            exc_info=True,
        )

    @responses.activate
    @patch.object(AdyenSubscription, 'renew')
    @patch('amuse.vendor.adyen.logger')
    def test_uncaught_error_sets_payment_status_if_missing(
        self, mock_logger, mock_renew
    ):
        payment = PaymentTransactionFactory(
            subscription=self.subscription, status=PaymentTransaction.STATUS_NOT_SENT
        )
        error_msg = 'Something broke!'

        def side_effect(*args, **kwargs):
            raise ValueError(error_msg)

        mock_renew.side_effect = side_effect
        self.assertIsNone(self.subscription.valid_until)

        response = renew_subscription(self.subscription)

        self.assertFalse(response['is_success'])
        self.payment.refresh_from_db()
        payment.refresh_from_db()
        self.subscription.refresh_from_db()
        self.assertEqual(self.payment.status, PaymentTransaction.STATUS_APPROVED)
        self.assertEqual(payment.status, PaymentTransaction.STATUS_ERROR)
        self.assertEqual(self.subscription.status, Subscription.STATUS_GRACE_PERIOD)
        mock_logger.error.assert_called_with(
            f'Uncaught exception occurred while renewing Subscription {self.subscription.pk}: {error_msg}',
            exc_info=True,
        )

    @responses.activate
    def test_fraud_payments_are_disabled_with_no_grace_period(self):
        self._add_checkout_response('Refused', is_renewal=True, refusal_reason='FRAUD')
        self.assertIsNone(self.subscription.valid_until)
        self.assertEqual(self.subscription.status, Subscription.STATUS_ACTIVE)

        response = renew_subscription(self.subscription)
        self.user.refresh_from_db()

        self.assertFalse(response['is_success'])
        self._assert_payment_and_subscription(
            payment_status=PaymentTransaction.STATUS_DECLINED,
            subscription_user_id=self.user.pk,
            subscription_status=Subscription.STATUS_EXPIRED,
        )
        self.assertNotEqual(self.subscription.status, Subscription.STATUS_GRACE_PERIOD)
        self.assertEqual(self.subscription.valid_until, self.subscription.paid_until)
        self.assertTrue(self.user.usermetadata.is_fraud_attempted)

    @responses.activate
    def test_non_renewable_prepaid_payments_are_disabled_with_no_grace_period(self):
        self._add_checkout_response(
            'Refused',
            is_renewal=True,
            refusal_reason='Not enough balance',
            additional_data={'fundingSource': 'PREPAID'},
        )
        self.assertIsNone(self.subscription.valid_until)
        self.assertEqual(self.subscription.status, Subscription.STATUS_ACTIVE)

        response = renew_subscription(self.subscription)

        self.assertFalse(response['is_success'])
        self._assert_payment_and_subscription(
            payment_status=PaymentTransaction.STATUS_DECLINED,
            subscription_user_id=self.user.pk,
            subscription_status=Subscription.STATUS_EXPIRED,
        )
        self.assertNotEqual(self.subscription.status, Subscription.STATUS_GRACE_PERIOD)
        self.assertEqual(self.subscription.valid_until, self.subscription.paid_until)

    @responses.activate
    @patch('amuse.vendor.segment.events._subscription_renewal_error')
    def test_payment_refused_insufficient_funds_triggers_cio_event(
        self, mocked_segment
    ):
        self._add_checkout_response(
            'Refused', is_renewal=True, refusal_reason='Not enough balance'
        )

        response = renew_subscription(self.subscription)

        self.assertFalse(response['is_success'])
        mocked_segment.assert_called_once_with(
            self.subscription,
            'payment_error_lack_of_funds',
            NONLOCALIZED_PAYMENTS_COUNTRY,
        )

    @responses.activate
    @patch('amuse.vendor.segment.events._subscription_renewal_error')
    def test_payment_refused_expired_card_detected_triggers_cio_event(
        self, mocked_segment
    ):
        payment_method = self.subscription.payment_method
        payment_method.expiry_date = timezone.now().date() - timedelta(days=10)
        payment_method.save()

        self._add_checkout_response('Refused', is_renewal=True)

        response = renew_subscription(self.subscription)

        self.assertFalse(response['is_success'])
        mocked_segment.assert_called_once_with(
            self.subscription,
            'payment_error_card_expired',
            NONLOCALIZED_PAYMENTS_COUNTRY,
        )

    @responses.activate
    @patch('amuse.vendor.segment.events._subscription_renewal_error')
    def test_payment_refused_expired_card_response_triggers_cio_event(
        self, mocked_segment
    ):
        self._add_checkout_response(
            'Refused', is_renewal=True, refusal_reason='Expired Card'
        )

        response = renew_subscription(self.subscription)

        self.assertFalse(response['is_success'])
        mocked_segment.assert_called_once_with(
            self.subscription,
            'payment_error_card_expired',
            NONLOCALIZED_PAYMENTS_COUNTRY,
        )

    @responses.activate
    def test_payment_error(self):
        self._add_checkout_response('Error', is_renewal=True)
        self.assertIsNone(self.subscription.valid_until)

        response = renew_subscription(self.subscription)

        self.assertFalse(response['is_success'])
        self._assert_renewal_added_transaction(subscription_active=False)
        self._assert_payment_and_subscription(
            payment_status=PaymentTransaction.STATUS_ERROR,
            subscription_user_id=self.user.pk,
            subscription_status=Subscription.STATUS_GRACE_PERIOD,
        )

    @responses.activate
    @patch('amuse.vendor.adyen.logger.exception')
    def test_payment_unsupported_status(self, mocked_logger):
        self._add_checkout_response('NewUnsupported', is_renewal=True)

        self.assertFalse(renew_subscription(self.subscription)['is_success'])
        self._assert_renewal_added_transaction(subscription_active=False)
        self._assert_payment_and_subscription(
            payment_status=PaymentTransaction.STATUS_ERROR,
            subscription_user_id=self.user.pk,
            subscription_status=Subscription.STATUS_GRACE_PERIOD,
        )
        mocked_logger.assert_called_once_with(
            'PaymentUnknownResponse for PaymentTransaction:%s'
            % PaymentTransaction.objects.last().pk
        )

    @responses.activate
    def test_payment_invalid_payment_details(self):
        external_payment_id = 'blahonga'
        self._add_error_response(external_payment_id)

        response = renew_subscription(self.subscription)
        payment = PaymentTransaction.objects.last()

        self.assertFalse(response['is_success'])
        self.assertEqual(payment.external_transaction_id, external_payment_id)
        self.assertEqual(payment.subscription.plan_id, self.plan.pk)
        self.assertEqual(payment.status, PaymentTransaction.STATUS_ERROR)
        self.assertEqual(payment.subscription.user_id, self.user.pk)
        self._assert_renewal_added_transaction(subscription_active=False)
