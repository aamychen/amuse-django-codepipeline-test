from decimal import Decimal
from unittest.mock import patch

from django.utils import timezone
from datetime import timedelta

from amuse.tests.test_api.base import AmuseAPITestCase
from amuse.vendor.appsflyer import events as af
from amuse.vendor.appsflyer.s2s_mobile import _get_event_value
from countries.tests.factories import CountryFactory, CurrencyFactory
from payments.models import PaymentTransaction
from payments.tests.factories import PaymentTransactionFactory
from releases.tests.factories import RoyaltySplitFactory
from subscriptions.tests.factories import (
    PriceCardFactory,
    SubscriptionPlanFactory,
    SubscriptionFactory,
)
from users.tests.factories import AppsflyerDeviceFactory, UserFactory


class TestCaseAppsFlyerEvents(AmuseAPITestCase):
    def setUp(self):
        self.user = UserFactory()
        self.device = AppsflyerDeviceFactory(appsflyer_id='web', user=self.user)

    def _is_event_data_json_serializable(self, event_data):
        # Test serialization of full event data sent to appsflyer
        try:
            _get_event_value(event_data)
        except TypeError as err:
            self.fail(f'_get_event_value() raised TypeError unexpectedly! Error: {err}')

    @patch('amuse.vendor.appsflyer.events.send_s2s')
    def test_email_verified(self, mock_s2s):
        af.email_verified(self.device, self.user.id)

        mock_s2s.assert_called_once_with(
            device=self.device,
            user_id=self.user.id,
            event_name='Email Verified',
            data={},
        )

    @patch('amuse.vendor.appsflyer.events.send_s2s')
    def test_ffwd_started(self, mock_s2s):
        af.ffwd_started(self.device, self.user, Decimal("12.34"))

        mock_s2s.assert_called_once_with(
            device=self.device,
            user_id=self.user.id,
            event_name='Ffwd Started',
            data={'withdrawal_amount': '12.34'},
        )

    @patch('amuse.vendor.appsflyer.events.send_s2s')
    def test_login_succeeded(self, mock_s2s):
        af.login_succeeded(self.device, self.user, data={'ip': '127.0.0.1'})

        mock_s2s.assert_called_once_with(
            device=self.device,
            user_id=self.user.id,
            event_name='login_succeeded',
            data={'ip': '127.0.0.1'},
        )

    @patch('amuse.vendor.appsflyer.events.send_s2s')
    def test_royalty_advance_notification(self, mock_s2s):
        af.royalty_advance_notification(self.device, self.user.id, 'ot', 12.34)

        mock_s2s.assert_called_once_with(
            device=self.device,
            user_id=self.user.id,
            event_name='ffwd_new_offer',
            data={'price': 12.34, 'offer_type': 'ot'},
        )

    @patch('amuse.vendor.appsflyer.events.send_s2s')
    def test_split_accepted(self, mock_s2s):
        split = RoyaltySplitFactory(user=self.user)

        af.split_accepted(self.device, split)

        mock_s2s.assert_called_once_with(
            device=self.device,
            user_id=split.user_id,
            event_name='split_accepted',
            data={'split_rate': str(split.rate), 'song_name': split.song.name},
        )

    @patch('amuse.vendor.appsflyer.events.send_s2s')
    def test_split_invites_expired(self, mock_s2s):
        af.split_invites_expired(self.device, self.user.id, 'song123')

        mock_s2s.assert_called_once_with(
            device=self.device,
            user_id=self.user.id,
            event_name='split_invites_expired',
            data={'song_name': 'song123'},
        )

    @patch('amuse.vendor.appsflyer.events.send_s2s')
    def test_subscription_canceled(self, mock_s2s):
        subscription = SubscriptionFactory(user=self.user, valid_until=timezone.now())

        af.subscription_canceled(self.device, subscription, '0.0.0.0')

        mock_s2s.assert_called_once_with(
            device=self.device,
            user_id=self.user.id,
            event_name='subscription_cancelled',
            data={
                'ip': '0.0.0.0',
                'plan_name': subscription.plan.name,
                'user_first_name': subscription.user.first_name,
                'subscription_plan_end_date': subscription.valid_until.isoformat(),
            },
        )

    @patch('amuse.vendor.appsflyer.events.send_s2s')
    def test_s4a_connected(self, mock_s2s):
        af.s4a_connected(self.device, self.user.id, 1234)

        mock_s2s.assert_called_once_with(
            device=self.device,
            user_id=self.user.id,
            event_name='s4a_complete',
            data={'artist_id': 1234},
        )

    @patch('amuse.vendor.appsflyer.events.send_s2s')
    def test_signup_completed(self, mock_s2s):
        platform_name = 'web'
        country = 'Congo, Democratic Republic of'
        signup_path = 'regular'
        af.signup_completed(
            self.device, self.user.id, platform_name, country, signup_path
        )

        mock_s2s.assert_called_once_with(
            device=self.device,
            user_id=self.user.id,
            event_name='Signup Completed',
            data={
                "country": country,
                "platform": platform_name,
                "signup_path": signup_path,
            },
        )

    @patch('amuse.vendor.appsflyer.events.send_s2s')
    def test_rb_successful(self, mock_s2s):
        platform_name = 'web'
        country = 'Congo, Democratic Republic of'
        release_date = timezone.now().date() + timedelta(days=10)
        release_date_iso = release_date.isoformat()
        event_data = {
            "release_id": 123,
            "release_name": 'Test Release',
            "main_primary_artist": 'New Artist',
            "release_date": release_date,
        }

        self._is_event_data_json_serializable(
            {
                "country": country,
                "platform_name": platform_name,
                "release_id": event_data['release_id'],
                "release_name": event_data['release_name'],
                "main_primary_artist": event_data['main_primary_artist'],
                "release_date": release_date_iso,
            }
        )

        af.rb_successful(self.device, self.user.id, platform_name, country, event_data)

        mock_s2s.assert_called_once_with(
            device=self.device,
            user_id=self.user.id,
            event_name='Rb Successful',
            data={
                "country": country,
                "platform": platform_name,
                "release_id": event_data['release_id'],
                "release_name": event_data['release_name'],
                "main_primary_artist": event_data['main_primary_artist'],
                "release_date": release_date_iso,
            },
        )


class TestCaseAppsFlyerSubscriptionEvents(AmuseAPITestCase):
    def setUp(self):
        self.user = UserFactory()
        self.device = AppsflyerDeviceFactory(appsflyer_id='web', user=self.user)

        self.plan = SubscriptionPlanFactory(create_card=False)
        self.subscription = SubscriptionFactory(
            user=self.user,
            plan=self.plan,
            grace_period_until=timezone.now(),
            valid_until=timezone.now(),
        )
        self.currency = CurrencyFactory(code='USD')
        self.country = CountryFactory(code='US')
        self.card = PriceCardFactory(
            price=12.34,
            plan=self.plan,
            currency=self.currency,
            countries=[self.country],
        )
        self.payment = PaymentTransactionFactory(
            subscription=self.subscription,
            plan=self.plan,
            user=self.user,
            country=self.country,
            currency=self.currency,
            amount=self.card.price,
            platform=PaymentTransaction.PLATFORM_IOS,
        )

    @patch('amuse.vendor.appsflyer.events.send_s2s')
    def test_subscription_changed(self, mock_s2s):
        new_plan = SubscriptionPlanFactory(create_card=False)
        new_card = PriceCardFactory(
            price=24, plan=new_plan, currency=self.currency, countries=[self.country]
        )
        previous_card = self.subscription.plan.get_price_card(country=self.country)

        af.subscription_changed(
            self.device, self.subscription, self.subscription.plan, new_plan, '0.0.0.0'
        )

        mock_s2s.assert_called_once_with(
            device=self.device,
            user_id=self.user.id,
            event_name='subscription_plan_changed_confirmation',
            data={
                'currency': new_card.currency.code,
                'ip': '0.0.0.0',
                'plan_name': self.plan.name,
                'price': '24.00',
                'current_subscription_plan_name': self.subscription.plan.name,
                'current_subscription_plan_price': previous_card.currency_and_price,
                'date_when_new_plan_will_become_active': self.subscription.paid_until.isoformat(),
                'new_subscription_plan_name': new_plan.name,
                'new_subscription_plan_price': 'USD 24.00',
                'user_first_name': self.subscription.user.first_name,
                'product': {
                    'name': new_plan.name,
                    'product_id': new_plan.pk,
                    'quantity': 1,
                },
                'revenue': '24.00',
                'total': '24.00',
            },
        )

    @patch('amuse.vendor.appsflyer.events.send_s2s')
    def test_tier_upgraded(self, mock_s2s):
        previous_plan = SubscriptionPlanFactory(create_card=False)
        previous_card = PriceCardFactory(
            price=12.34,
            plan=previous_plan,
            currency=self.currency,
            countries=[self.country],
        )
        transaction = PaymentTransactionFactory(subscription=self.subscription)
        af.subscription_tier_upgraded(
            self.device, self.subscription, previous_plan, '0.0.0.0'
        )

        mock_s2s.assert_called_once_with(
            device=self.device,
            user_id=self.user.id,
            event_name='subscription_plan_changed_confirmation',
            data={
                'currency': transaction.currency.code,
                'ip': '0.0.0.0',
                'plan_name': self.plan.name,
                'price': str(transaction.amount),
                'current_subscription_plan_name': previous_plan.name,
                'current_subscription_plan_price': previous_card.currency_and_price,
                'date_when_new_plan_will_become_active': timezone.now()
                .date()
                .isoformat(),
                'new_subscription_plan_name': self.subscription.plan.name,
                'new_subscription_plan_price': f'{transaction.currency.code} {transaction.amount}',
                'user_first_name': self.subscription.user.first_name,
                'product': {
                    'name': self.subscription.plan.name,
                    'product_id': self.subscription.plan_id,
                    'quantity': 1,
                },
                'revenue': str(transaction.amount),
                'total': str(transaction.amount),
            },
        )

    @patch('amuse.vendor.appsflyer.events.send_s2s')
    def test_subscription_new_intro_started(self, mock_s2s):
        af.subscription_new_intro_started(self.device, self.subscription, '0.0.0.0')

        mock_s2s.assert_called_once_with(
            device=self.device,
            user_id=self.user.id,
            event_name='Subscription IntroStarted',
            data={
                'currency': 'USD',
                'ip': '0.0.0.0',
                'plan_name': self.plan.name,
                'price': '12.34',
                'user_first_name': self.subscription.user.first_name,
                'subscription_plan_name': self.subscription.plan.name,
                'subscription_plan_price': self.card.currency_and_price,
                'renewal_date': self.subscription.paid_until.isoformat(),
                'product': {
                    'name': self.subscription.plan.name,
                    'product_id': self.subscription.plan_id,
                    'quantity': 1,
                },
                'revenue': str(self.card.price),
                'total': str(self.card.price),
                'af_revenue': str(self.card.price),
                'af_currency': 'USD',
                'af_content_id': self.subscription.plan_id,
                'af_quantity': 1,
                'tier': 'Pro',
                'platform': 'ios',
            },
        )

    @patch('amuse.vendor.appsflyer.events.send_s2s')
    def test_subscription_new_started(self, mock_s2s):
        af.subscription_new_started(self.device, self.subscription, '0.0.0.0')

        mock_s2s.assert_called_once_with(
            device=self.device,
            user_id=self.user.id,
            event_name='Subscription Started',
            data={
                'currency': 'USD',
                'ip': '0.0.0.0',
                'plan_name': self.plan.name,
                'price': '12.34',
                'user_first_name': self.subscription.user.first_name,
                'subscription_plan_name': self.subscription.plan.name,
                'subscription_plan_price': self.card.currency_and_price,
                'renewal_date': self.subscription.paid_until.isoformat(),
                'product': {
                    'name': self.subscription.plan.name,
                    'product_id': self.subscription.plan_id,
                    'quantity': 1,
                },
                'revenue': str(self.card.price),
                'total': str(self.card.price),
                'af_revenue': str(self.card.price),
                'af_currency': 'USD',
                'af_content_id': self.subscription.plan_id,
                'af_quantity': 1,
                'tier': 'Pro',
                'platform': 'ios',
            },
        )

    @patch('amuse.vendor.appsflyer.events.send_s2s')
    def test_subscription_payment_method_changed(self, mock_s2s):
        af.subscription_payment_method_changed(
            self.device, self.subscription, '0.0.0.0'
        )

        mock_s2s.assert_called_once_with(
            device=self.device,
            user_id=self.user.id,
            event_name='payment_method_updated',
            data={
                'ip': '0.0.0.0',
                'user_first_name': self.subscription.user.first_name,
                'subscription_plan_name': self.subscription.plan.name,
            },
        )

    @patch('amuse.vendor.appsflyer.events.send_s2s')
    def test_subscription_payment_method_expired(self, mock_s2s):
        af.subscription_payment_method_expired(self.device, self.subscription)

        mock_s2s.assert_called_once_with(
            device=self.device,
            user_id=self.user.id,
            event_name='payment_error_card_expired',
            data={
                'user_first_name': self.subscription.user.first_name,
                'subscription_plan_name': self.subscription.plan.name,
                'subscription_plan_price': self.card.currency_and_price,
                'subscription_plan_grace_period': self.subscription.grace_period_until.isoformat(),
            },
        )

    @patch('amuse.vendor.appsflyer.events.send_s2s')
    def test_subscription_renewal_error(self, mock_s2s):
        af.subscription_renewal_error(self.device, self.subscription)

        mock_s2s.assert_called_once_with(
            device=self.device,
            user_id=self.user.id,
            event_name='payment_error_generic',
            data={
                'user_first_name': self.subscription.user.first_name,
                'subscription_plan_name': self.subscription.plan.name,
                'subscription_plan_price': self.card.currency_and_price,
                'subscription_plan_grace_period': self.subscription.grace_period_until.isoformat(),
            },
        )

    @patch('amuse.vendor.appsflyer.events.send_s2s')
    def test_subscription_renewal_error_lack_of_funds(self, mock_s2s):
        af.subscription_renewal_error_lack_of_funds(self.device, self.subscription)

        mock_s2s.assert_called_once_with(
            device=self.device,
            user_id=self.user.id,
            event_name='payment_error_lack_of_funds',
            data={
                'user_first_name': self.subscription.user.first_name,
                'subscription_plan_name': self.subscription.plan.name,
                'subscription_plan_price': self.card.currency_and_price,
                'subscription_plan_grace_period': self.subscription.grace_period_until.isoformat(),
            },
        )

    @patch('amuse.vendor.appsflyer.events.send_s2s')
    def test_subscription_successful_renewal(self, mock_s2s):
        af.subscription_successful_renewal(
            self.device, self.subscription, self.card.price, self.card.currency.code
        )

        mock_s2s.assert_called_once_with(
            device=self.device,
            user_id=self.user.id,
            event_name='subscription_successful_renewal',
            data={
                'currency': self.card.currency.code,
                'plan_name': self.subscription.plan.name,
                'price': str(self.card.price),
                'current_subscription_plan_name': self.subscription.plan.name,
                'current_subscription_plan_price': self.card.currency_and_price,
                'user_first_name': self.subscription.user.first_name,
                'product': {
                    'name': self.subscription.plan.name,
                    'product_id': self.subscription.plan_id,
                    'quantity': 1,
                },
                'revenue': str(self.card.price),
                'total': str(self.card.price),
            },
        )

    @patch('amuse.vendor.appsflyer.events.send_s2s')
    def test_subscription_trial_started(self, mock_s2s):
        af.subscription_trial_started(self.device, self.subscription, '0.0.0.0', 'USD')

        mock_s2s.assert_called_once_with(
            device=self.device,
            user_id=self.user.id,
            event_name='Subscription TrialStarted',
            data={
                'currency': 'USD',
                'ip': '0.0.0.0',
                'plan_name': self.plan.name,
                'price': '12.34',
                'user_first_name': self.subscription.user.first_name,
                'subscription_plan_name': self.subscription.plan.name,
                'subscription_plan_price': self.card.currency_and_price,
                'renewal_date': self.subscription.paid_until.isoformat(),
                'product': {
                    'name': self.subscription.plan.name,
                    'product_id': self.subscription.plan_id,
                    'quantity': 1,
                },
                'revenue': str(self.card.price),
                'total': str(self.card.price),
                'af_revenue': str(self.card.price),
                'af_currency': 'USD',
                'af_content_id': self.subscription.plan_id,
                'af_quantity': 1,
                'tier': 'Pro',
                'platform': 'ios',
            },
        )
