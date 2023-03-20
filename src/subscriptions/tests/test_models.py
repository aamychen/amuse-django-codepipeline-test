from datetime import timedelta
from unittest.mock import patch

import responses
from django.core.exceptions import ValidationError
from django.test import TestCase, override_settings

from amuse.tests.helpers import (
    ZENDESK_MOCK_API_URL_TOKEN,
    add_zendesk_mock_post_response,
)
from countries.tests.factories import CountryFactory
from payments.models import PaymentTransaction
from payments.tests.factories import PaymentTransactionFactory
from subscriptions.models import Subscription
from subscriptions.tests.factories import (
    SubscriptionFactory,
    SubscriptionPlanFactory,
    PriceCardFactory,
)
from users.tests.factories import UserFactory


@override_settings(**ZENDESK_MOCK_API_URL_TOKEN)
class SubscriptionModelsTest(TestCase):
    @responses.activate
    def setUp(self):
        add_zendesk_mock_post_response()
        self.subscription = SubscriptionFactory()

    def test_to_string(self):
        assert str(self.subscription)

    def test_latest_payment(self):
        payment = PaymentTransactionFactory(
            subscription=self.subscription, user=self.subscription.user
        )
        # Create other PaymentTransactions that should not be returned
        PaymentTransactionFactory(
            subscription=self.subscription,
            user=self.subscription.user,
            type=PaymentTransaction.TYPE_UNKNOWN,
        )
        PaymentTransactionFactory(
            subscription=self.subscription,
            user=self.subscription.user,
            type=PaymentTransaction.TYPE_PAYMENT,
            status=PaymentTransaction.STATUS_ERROR,
        )

        self.assertEqual(self.subscription.latest_payment().pk, payment.pk)

    def test_price_card_sets_correct_price_adyen(self):
        card = PriceCardFactory()
        self.assertEqual(
            card.price_adyen, int(card.price * pow(10, card.currency.decimals))
        )

    def test_price_card_currency_and_price(self):
        card = PriceCardFactory()
        self.assertEqual(card.currency_and_price, f'{card.currency.code} {card.price}')

    def test_price_card_period_price(self):
        card = PriceCardFactory()
        self.assertEqual(
            card.period_price, str(round(card.price / card.plan.period, 2))
        )

    def test_price_card_missing_raises_error(self):
        plan = SubscriptionPlanFactory()
        plan.get_price_card().delete()
        with self.assertRaises(ValueError) as err:
            plan.get_price_card()
        self.assertIn('No PriceCard found', str(err.exception))

    def test_price_card_limit_one_per_plan_per_country(self):
        country = CountryFactory(code='NA')
        plan = SubscriptionPlanFactory(countries=[country])
        card = PriceCardFactory(plan=plan, countries=[country])
        with self.assertRaises(ValueError) as err:
            plan.get_price_card(country=country.code)
        self.assertIn('More than one PriceCard found', str(err.exception))

    @responses.activate
    def test_subscription_validation(self):
        add_zendesk_mock_post_response()
        self.subscription.valid_until = self.subscription.valid_from - timedelta(
            days=10
        )

        with self.assertRaises(ValidationError) as context:
            self.subscription.clean()

        self.assertEqual(
            context.exception.error_dict['valid_until'][0].message,
            "Must be after 'valid_from'",
        )

    def test_get_current_plan_with_payment_returns_plan_from_payment(self):
        payment = PaymentTransactionFactory(
            subscription=self.subscription,
            user=self.subscription.user,
            type=PaymentTransaction.TYPE_PAYMENT,
        )

        self.assertEqual(self.subscription.get_current_plan(), payment.plan)

    def test_get_current_plan_defaults_to_subscription_plan(self):
        self.assertEqual(self.subscription.get_current_plan(), self.subscription.plan)

    def test_get_current_plan_handles_trial_subscriptions(self):
        trial_auth = PaymentTransactionFactory(
            subscription=self.subscription,
            user=self.subscription.user,
            type=PaymentTransaction.TYPE_AUTHORISATION,
        )
        reactivate_auth = PaymentTransactionFactory(
            subscription=self.subscription,
            user=self.subscription.user,
            type=PaymentTransaction.TYPE_AUTHORISATION,
        )

        self.assertEqual(self.subscription.get_current_plan(), trial_auth.plan)

    def test_get_current_plan_handles_multiple_cancel_reactivate(self):
        trial_auth = PaymentTransactionFactory(
            subscription=self.subscription,
            user=self.subscription.user,
            type=PaymentTransaction.TYPE_AUTHORISATION,
        )
        reactivate_auth = PaymentTransactionFactory(
            subscription=self.subscription,
            user=self.subscription.user,
            type=PaymentTransaction.TYPE_AUTHORISATION,
        )
        reactivate_auth_2 = PaymentTransactionFactory(
            subscription=self.subscription,
            user=self.subscription.user,
            type=PaymentTransaction.TYPE_AUTHORISATION,
        )

        self.assertEqual(self.subscription.get_current_plan(), trial_auth.plan)

    def test_get_apple_receipt(self):
        payment = PaymentTransactionFactory(subscription=self.subscription)
        receipt = self.subscription.apple_receipt()
        assert receipt == None
        payment.customer_payment_payload = {'receipt_data': "=dsfk3i5hetr"}
        payment.save()
        receipt = self.subscription.apple_receipt()
        assert receipt == "=dsfk3i5hetr"

    @patch('subscriptions.models.logger')
    def test_get_apple_receipt_no_payments_case(self, mocked_logger):
        receipt = self.subscription.apple_receipt()
        assert receipt == None
        mocked_logger.warning.assert_called_once_with(
            f"Apple subscription {self.subscription.pk} has no valid payments"
        )


@override_settings(**ZENDESK_MOCK_API_URL_TOKEN)
class SubscriptionModelsIsFreeTest(TestCase):
    @responses.activate
    def setUp(self):
        add_zendesk_mock_post_response()

    def test_is_free(self):
        plan = SubscriptionPlanFactory(price=0)
        subscription = SubscriptionFactory(plan=plan)
        self.assertTrue(subscription.is_free)

    def test_is_not_free(self):
        plan = SubscriptionPlanFactory(price=10.0)
        subscription = SubscriptionFactory(plan=plan)
        self.assertFalse(subscription.is_free)


@override_settings(**ZENDESK_MOCK_API_URL_TOKEN)
class SubscriptionPostSaveTestCase(TestCase):
    @responses.activate
    def setUp(self):
        add_zendesk_mock_post_response()
        self.subscription = SubscriptionFactory(user__zendesk_id=12345)
        self.user = self.subscription.user

    @patch('subscriptions.models.settings')
    def test_subscription_post_save(self, mocked_settings):
        mocked_settings.DEBUG = False
        with patch('amuse.tasks.zendesk_create_or_update_user.delay') as mocked_zendesk:
            self.subscription.save()

        mocked_zendesk.assert_called_once_with(self.user.pk)

    @patch('subscriptions.models.settings')
    @patch('subscriptions.models.logger.warning')
    def test_subscription_post_save_exception_handling(
        self, mocked_logger, mocked_settings
    ):
        mocked_settings.DEBUG = False

        with patch('amuse.tasks.zendesk_create_or_update_user.delay') as mocked_zendesk:
            mocked_zendesk.side_effect = Exception('hello')
            self.subscription.save()

        mocked_logger.assert_called_once_with(
            f'Unable to update Zendesk User status for Subscription: {self.subscription.pk} and User: {self.user.pk} with error: hello'
        )


@override_settings(**ZENDESK_MOCK_API_URL_TOKEN)
class SubscriptionPostSaveUpdatesSegmentTestCase(TestCase):
    OVERRIDE_SEGMENT_UPDATE_IS_PRO_STATE = {'SEGMENT_UPDATE_IS_PRO_STATE': True}

    @responses.activate
    def setUp(self):
        add_zendesk_mock_post_response()
        self.user = UserFactory()
        self.subscription = SubscriptionFactory(user=self.user)

    @override_settings(**OVERRIDE_SEGMENT_UPDATE_IS_PRO_STATE)
    @patch('amuse.vendor.segment.events.update_is_pro_state')
    def test_post_save_updates_segment_user(self, mock_update_pro):
        self.subscription.save()
        mock_update_pro.assert_called_with(self.user)

    @override_settings(**OVERRIDE_SEGMENT_UPDATE_IS_PRO_STATE)
    @patch('amuse.vendor.segment.events.update_is_pro_state')
    @patch('subscriptions.models.logger.warning')
    def test_subscription_post_save_segment_exception_handling(
        self, mocked_logger, mock_update_pro
    ):
        ex = Exception('hello')
        mock_update_pro.side_effect = ex
        self.subscription.save()

        mocked_logger.assert_called_once_with(
            f'Unable to update Segment User: {self.user.id}', ex
        )

    @patch('amuse.analytics.update_is_pro_state')
    def test_post_save_does_not_update_segment_user_if_disabled(self, mock_update_pro):
        self.subscription.save()
        self.assertEqual(0, mock_update_pro.call_count)
