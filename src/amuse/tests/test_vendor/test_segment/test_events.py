from datetime import datetime
from datetime import timedelta
from unittest.mock import patch

import factory
import pytest
from django.test import TestCase
from django.utils import timezone

from amuse.vendor.segment.events import (
    email_verified,
    ffwd_started,
    split_accepted,
    split_invites_expired,
    subscription_canceled,
    subscription_changed,
    subscription_tier_upgraded,
    subscription_new_intro_started,
    subscription_new_started,
    subscription_trial_started,
    subscription_payment_method_changed,
    subscription_payment_method_expired,
    subscription_renewal_error_lack_of_funds,
    subscription_successful_renewal,
    update_is_pro_state,
    s4a_connected,
    send_smart_link_release_email,
    send_smart_link_delivered_email,
    signup_completed,
    send_rb_successful,
    send_release_approved,
    send_release_not_approved,
    send_release_rejected,
    send_release_taken_down,
    send_release_deleted,
    send_release_released,
    send_release_delivered,
    send_release_undeliverable,
    identify_user,
    user_requested_account_delete,
    track,
    identify,
)
from countries.tests.factories import CountryFactory, CurrencyFactory
from payments.models import PaymentTransaction
from payments.tests.factories import PaymentTransactionFactory
from releases.tests.factories import RoyaltySplitFactory
from subscriptions.tests.factories import (
    SubscriptionFactory,
    SubscriptionPlanFactory,
    PriceCardFactory,
)
from users.models import User
from users.tests.factories import UserFactory

WAFFLE_SAMPLE_KEY = 'segment:celery:enabled'


class IsProTestCase(TestCase):
    @patch('amuse.vendor.zendesk.api.create_or_update_user')
    def setUp(self, mock_zendesk_user):
        self.subscription = SubscriptionFactory()
        self.client = 'test'
        self.ip = '127.0.0.1'

    @patch('amuse.vendor.zendesk.api.create_or_update_user')
    @patch('amuse.vendor.segment.events.identify')
    def test_update_is_pro_state(self, mock_identify, mock_zendesk):
        user = UserFactory()
        update_is_pro_state(user)
        self.assertEqual(1, mock_identify.call_count)

    @patch('amuse.vendor.segment.events.identify')
    def test_update_is_pro_state_unknown_user(self, mock_identify):
        user = User()
        update_is_pro_state(user)
        self.assertEqual(0, mock_identify.call_count)


class SubscriptionEventsTestCase(TestCase):
    @patch('amuse.vendor.zendesk.api.create_or_update_user')
    def setUp(self, mock_zendesk_user):
        user = UserFactory()
        plan = SubscriptionPlanFactory()
        card = plan.get_price_card()
        currency = card.currency
        country = card.countries.first()

        self.subscription = SubscriptionFactory(user=user, plan=plan)
        self.payment = PaymentTransactionFactory(
            subscription=self.subscription,
            plan=plan,
            user=user,
            country=country,
            currency=currency,
            amount=card.price,
            platform=PaymentTransaction.PLATFORM_ANDROID,
        )

        self.client = 'test'
        self.ip = '127.0.0.1'

    @patch('amuse.vendor.segment.events.track')
    def test_renewal_error_lack_of_funds(self, mock_track):
        self.subscription.grace_period_until = timezone.now().date()
        card = self.subscription.plan.get_price_card()

        subscription_renewal_error_lack_of_funds(self.subscription)

        mock_track.assert_called_once_with(
            self.subscription.user_id,
            'payment_error_lack_of_funds',
            properties={
                'user_first_name': self.subscription.user.first_name,
                'subscription_plan_name': self.subscription.plan.name,
                'subscription_plan_price': card.currency_and_price,
                'subscription_plan_grace_period': self.subscription.grace_period_until.isoformat(),
            },
        )

    @patch('amuse.vendor.segment.events.track')
    def test_payment_method_expired(self, mock_track):
        card = self.subscription.plan.get_price_card()
        self.subscription.grace_period_until = timezone.now().date()

        subscription_payment_method_expired(self.subscription)

        mock_track.assert_called_once_with(
            self.subscription.user_id,
            'payment_error_card_expired',
            properties={
                'user_first_name': self.subscription.user.first_name,
                'subscription_plan_name': self.subscription.plan.name,
                'subscription_plan_price': card.currency_and_price,
                'subscription_plan_grace_period': self.subscription.grace_period_until.isoformat(),
            },
        )

    @patch('amuse.vendor.segment.events.track')
    def test_payment_method_changed(self, mock_track):
        subscription_payment_method_changed(self.subscription, self.client, self.ip)

        mock_track.assert_called_once_with(
            self.subscription.user_id,
            'payment_method_updated',
            properties={
                'user_first_name': self.subscription.user.first_name,
                'subscription_plan_name': self.subscription.plan.name,
            },
            context={'client': self.client, 'ip': self.ip},
        )

    @patch('amuse.vendor.segment.events.track')
    def test_canceled(self, mock_track):
        self.subscription.valid_until = timezone.now().date()

        subscription_canceled(self.subscription, self.client, self.ip)

        mock_track.assert_called_once_with(
            self.subscription.user_id,
            'subscription_cancelled',
            properties={
                'user_first_name': self.subscription.user.first_name,
                'subscription_plan_end_date': self.subscription.valid_until.isoformat(),
            },
            context={'client': self.client, 'ip': self.ip},
        )

    @patch('amuse.vendor.segment.events.track')
    def test_changed(self, mock_track):
        previous_plan = SubscriptionPlanFactory()
        previous_card = previous_plan.get_price_card()
        card = self.subscription.plan.get_price_card()
        currency = CurrencyFactory(code='USD')
        country = CountryFactory(code='US')

        new_plan = SubscriptionPlanFactory(create_card=False)
        new_card = PriceCardFactory(
            price=24, plan=new_plan, currency=currency, countries=[country]
        )

        subscription_changed(
            self.subscription, previous_plan, new_plan, self.client, self.ip
        )

        mock_track.assert_called_once_with(
            self.subscription.user_id,
            'subscription_plan_changed_confirmation',
            properties={
                'current_subscription_plan_name': previous_plan.name,
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
            context={'client': self.client, 'ip': self.ip},
        )

    @patch('amuse.vendor.segment.events.track')
    def test_tier_upgraded(self, mock_track):
        previous_plan = SubscriptionPlanFactory()
        previous_card = previous_plan.get_price_card()
        card = self.subscription.plan.get_price_card()
        transaction = PaymentTransactionFactory(subscription=self.subscription)

        subscription_tier_upgraded(
            self.subscription, previous_plan, self.client, self.ip
        )

        mock_track.assert_called_once_with(
            self.subscription.user_id,
            'subscription_plan_changed_confirmation',
            properties={
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
            context={'client': self.client, 'ip': self.ip},
        )

    @patch('amuse.vendor.segment.events.track')
    def test_new_subscription_intro_started(self, mock_track):
        subscription_new_intro_started(self.subscription, self.client, self.ip)

        payment = self.subscription.latest_payment()

        mock_track.assert_called_once_with(
            self.subscription.user_id,
            'Subscription IntroStarted',
            properties={
                'subscription_plan_name': self.subscription.plan.name,
                'subscription_plan_price': f'{payment.currency.code} {str(payment.amount)}',
                'renewal_date': self.subscription.paid_until.isoformat(),
                'user_first_name': self.subscription.user.first_name,
                'product': {
                    'name': self.subscription.plan.name,
                    'product_id': self.subscription.plan_id,
                    'quantity': 1,
                },
                'revenue': str(payment.amount),
                'total': str(payment.amount),
                'tier': 'Pro',
                'platform': 'android',
            },
            context={'client': self.client, 'ip': self.ip},
        )

    @patch('amuse.vendor.segment.events.track')
    def test_new_subscription_started(self, mock_track):
        subscription_new_started(self.subscription, self.client, self.ip)

        card = self.subscription.plan.get_price_card()

        mock_track.assert_called_once_with(
            self.subscription.user_id,
            'Subscription Started',
            properties={
                'subscription_plan_name': self.subscription.plan.name,
                'subscription_plan_price': card.currency_and_price,
                'renewal_date': self.subscription.paid_until.isoformat(),
                'user_first_name': self.subscription.user.first_name,
                'product': {
                    'name': self.subscription.plan.name,
                    'product_id': self.subscription.plan_id,
                    'quantity': 1,
                },
                'revenue': str(card.price),
                'total': str(card.price),
                'tier': 'Pro',
                'platform': 'android',
            },
            context={'client': self.client, 'ip': self.ip},
        )

    @patch('amuse.vendor.segment.events.track')
    def test_subscription_successful_renewal(self, mock_track):
        card = self.subscription.plan.get_price_card()
        subscription_successful_renewal(
            self.subscription, card.price, card.currency.code
        )

        mock_track.assert_called_once_with(
            self.subscription.user_id,
            'subscription_successful_renewal',
            properties={
                'current_subscription_plan_name': self.subscription.plan.name,
                'current_subscription_plan_price': card.currency_and_price,
                'user_first_name': self.subscription.user.first_name,
                'product': {
                    'name': self.subscription.plan.name,
                    'product_id': self.subscription.plan_id,
                    'quantity': 1,
                },
                'revenue': str(card.price),
                'total': str(card.price),
            },
        )

    @patch('amuse.vendor.segment.events.track')
    def test_trial_subscription_started(self, mock_track):
        subscription_trial_started(self.subscription, self.client, self.ip, 'USD')

        card = self.subscription.plan.get_price_card()

        mock_track.assert_called_once_with(
            self.subscription.user_id,
            'Subscription TrialStarted',
            properties={
                'subscription_plan_name': self.subscription.plan.name,
                'subscription_plan_price': card.currency_and_price,
                'renewal_date': self.subscription.paid_until.isoformat(),
                'user_first_name': self.subscription.user.first_name,
                'product': {
                    'name': self.subscription.plan.name,
                    'product_id': self.subscription.plan_id,
                    'quantity': 1,
                },
                'revenue': str(card.price),
                'total': str(card.price),
                'tier': 'Pro',
                'platform': 'android',
            },
            context={'client': self.client, 'ip': self.ip},
        )


@pytest.mark.django_db
@patch('amuse.vendor.segment.events.logger.info')
@patch('amuse.vendor.segment.events.track')
def test_email_verified(mock_track, mock_logger):
    user_id = factory.Faker('pyint')

    email_verified(user_id)

    mock_track.assert_called_once_with(user_id, 'Email Verified', properties={})
    mock_logger.assert_called_once()


@pytest.mark.django_db
@patch('amuse.vendor.zendesk.api.create_or_update_user')
@patch('amuse.vendor.segment.events.track')
def test_royalty_split_accepted(mock_track, mock_zendesk):
    split = RoyaltySplitFactory()

    split_accepted(split)

    mock_track.assert_called_once_with(
        split.user_id,
        'split_accepted',
        properties={
            'user_id': split.user_id,
            'split_rate': str(split.rate),
            'song_name': split.song.name,
        },
    )


@pytest.mark.django_db
@patch('amuse.vendor.segment.events.logger.info')
@patch('amuse.vendor.segment.events.track')
def test_split_invites_expired(mock_track, mock_logger):
    user_id = 9874523
    song_name = factory.Faker('name')

    split_invites_expired(user_id, song_name)

    mock_track.assert_called_once_with(
        user_id, 'split_invites_expired', properties={'song_name': song_name}
    )
    mock_logger.assert_called_once()


@pytest.mark.django_db
@patch('amuse.vendor.segment.events.logger.info')
@patch('amuse.vendor.segment.events.track')
def test_ffwd_started(mock_track, mock_logger):
    user_id = 9874523
    withdrawal_amount = 10.12

    ffwd_started(user_id, withdrawal_amount)

    mock_track.assert_called_once_with(
        user_id, 'Ffwd Started', properties={'withdrawal_amount': withdrawal_amount}
    )
    mock_logger.assert_called_once()


@pytest.mark.django_db
@patch('amuse.vendor.segment.events.track')
def test_s4a_connected(mock_track):
    user_id = 9874523
    artist_id = 1234

    s4a_connected(user_id, artist_id)

    mock_track.assert_called_once_with(
        user_id, 's4a_complete', properties={'artist_id': artist_id}
    )


@patch('amuse.vendor.segment.events.logger.info')
@patch('amuse.vendor.segment.events.track')
def test_send_smart_link_release_email(mock_track, logger_info_mock):
    mock_user_id = 1234
    mock_smart_link = 'https://share.amuse.io'
    send_smart_link_release_email(mock_user_id, mock_smart_link)
    mock_track.assert_called_once_with(
        mock_user_id, 'smart_link_release_email', properties={'url': mock_smart_link}
    )
    logger_info_mock.assert_called_once_with(
        f'Segment smart_link_release_email event for user_id: {mock_user_id}, '
        f'smart_link: {mock_smart_link}'
    )


@patch("amuse.vendor.segment.events.track")
def test_send_smart_link_delivered_email(mock_track):
    user_id = 123
    link = "https://example.com"
    include_pre_save_url = True
    mock_store_flags_dict = {
        "apple": False,
        "deezer": False,
        "spotify": False,
        "youtube_music": False,
        "tidal": False,
    }

    send_smart_link_delivered_email(
        user_id, link, include_pre_save_url, mock_store_flags_dict
    )
    mock_track_data = {
        "url": link,
        "include_pre_save_url": include_pre_save_url,
        "apple": False,
        "deezer": False,
        "spotify": False,
        "youtube_music": False,
        "tidal": False,
    }
    mock_track.assert_called_once_with(
        user_id, "smart_link_delivered_email", properties=mock_track_data
    )


@patch('amuse.vendor.segment.events.logger.info')
@patch("amuse.vendor.segment.events.track")
def test_signup_completed(mock_track, mock_logger):
    user_id = 123
    platform_name = 'web'
    country = 'Bosnia and Herzegovina'
    signup_path = 'regular'

    signup_completed(user_id, platform_name, country, signup_path)

    mock_track_data = {
        'signup_path': signup_path,
        'platform': platform_name,
        'country': country,
    }

    mock_track.assert_called_once_with(
        user_id, "Signup Completed", properties=mock_track_data
    )
    mock_logger.assert_called_once()


@patch('amuse.vendor.segment.events.logger.info')
@patch("amuse.vendor.segment.events.track")
def test_send_rb_successful(mock_track, mock_logger):
    user_id = 123
    release_id = 555
    platform_name = 'web'
    country = 'Bosnia and Herzegovina'
    release_name = "Test Release"
    main_artist_name = "Famous Artist"
    release_date = timezone.now().date() + timedelta(days=10)

    event_data = {
        "release_id": release_id,
        "release_name": release_name,
        "main_primary_artist": main_artist_name,
        "release_date": release_date,
    }

    send_rb_successful(user_id, platform_name, country, event_data)

    mock_track_data = {
        'platform': platform_name,
        'country': country,
        'release_id': release_id,
        'release_name': release_name,
        'main_primary_artist': main_artist_name,
        'release_date': release_date,
    }

    mock_track.assert_called_once_with(
        user_id, "Rb Successful", properties=mock_track_data
    )
    mock_logger.assert_called_once()


@patch('amuse.vendor.segment.events.logger.info')
@patch("amuse.vendor.segment.events.track")
def test_send_release_approved(mock_track, mock_logger):
    owner_id = 123
    release_id = 555
    release_name = "Test Release"
    main_artist_name = "Famous Artist"
    release_date = timezone.now().date() + timedelta(days=10)

    event_data = {
        "owner_id": owner_id,
        "release_id": release_id,
        "release_name": release_name,
        "main_primary_artist": main_artist_name,
        "release_date": release_date,
    }

    send_release_approved(event_data)

    mock_track_data = {
        "release_id": release_id,
        "release_name": release_name,
        "main_primary_artist": main_artist_name,
        "release_date": release_date,
    }

    mock_track.assert_called_once_with(
        owner_id, "Release Approved", properties=mock_track_data
    )
    mock_logger.assert_called_once()


@patch('amuse.vendor.segment.events.logger.info')
@patch("amuse.vendor.segment.events.track")
def test_send_release_not_approved(mock_track, mock_logger):
    owner_id = 123
    release_id = 555
    release_name = "Test Release"
    main_artist_name = "Famous Artist"
    release_date = timezone.now().date() + timedelta(days=10)

    event_data = {
        "owner_id": owner_id,
        "release_id": release_id,
        "release_name": release_name,
        "main_primary_artist": main_artist_name,
        "release_date": release_date,
    }

    send_release_not_approved(event_data)

    mock_track_data = {
        "release_id": release_id,
        "release_name": release_name,
        "main_primary_artist": main_artist_name,
        "release_date": release_date,
    }

    mock_track.assert_called_once_with(
        owner_id, "Release Not Approved", properties=mock_track_data
    )
    mock_logger.assert_called_once()


@patch('amuse.vendor.segment.events.logger.info')
@patch("amuse.vendor.segment.events.track")
def test_send_release_rejected(mock_track, mock_logger):
    owner_id = 123
    release_id = 555
    release_name = "Test Release"
    main_artist_name = "Famous Artist"
    release_date = timezone.now().date() + timedelta(days=10)

    event_data = {
        "owner_id": owner_id,
        "release_id": release_id,
        "release_name": release_name,
        "main_primary_artist": main_artist_name,
        "release_date": release_date,
    }

    send_release_rejected(event_data)

    mock_track_data = {
        "release_id": release_id,
        "release_name": release_name,
        "main_primary_artist": main_artist_name,
        "release_date": release_date,
    }

    mock_track.assert_called_once_with(
        owner_id, "Release Rejected", properties=mock_track_data
    )
    mock_logger.assert_called_once()


@patch('amuse.vendor.segment.events.logger.info')
@patch("amuse.vendor.segment.events.track")
def test_send_release_taken_down(mock_track, mock_logger):
    owner_id = 123
    release_id = 555
    release_name = "Test Release"
    main_artist_name = "Famous Artist"
    release_date = timezone.now().date() + timedelta(days=10)

    event_data = {
        "owner_id": owner_id,
        "release_id": release_id,
        "release_name": release_name,
        "main_primary_artist": main_artist_name,
        "release_date": release_date,
    }

    send_release_taken_down(event_data)

    mock_track_data = {
        "release_id": release_id,
        "release_name": release_name,
        "main_primary_artist": main_artist_name,
        "release_date": release_date,
    }

    mock_track.assert_called_once_with(
        owner_id, "Release Taken Down", properties=mock_track_data
    )
    mock_logger.assert_called_once()


@patch('amuse.vendor.segment.events.logger.info')
@patch("amuse.vendor.segment.events.track")
def test_send_release_deleted(mock_track, mock_logger):
    owner_id = 123
    release_id = 555
    release_name = "Test Release"
    main_artist_name = "Famous Artist"
    release_date = timezone.now().date() + timedelta(days=10)

    event_data = {
        "owner_id": owner_id,
        "release_id": release_id,
        "release_name": release_name,
        "main_primary_artist": main_artist_name,
        "release_date": release_date,
    }

    send_release_deleted(event_data)

    mock_track_data = {
        "release_id": release_id,
        "release_name": release_name,
        "main_primary_artist": main_artist_name,
        "release_date": release_date,
    }

    mock_track.assert_called_once_with(
        owner_id, "Release Deleted", properties=mock_track_data
    )
    mock_logger.assert_called_once()


@patch('amuse.vendor.segment.events.logger.info')
@patch("amuse.vendor.segment.events.track")
def test_send_release_released(mock_track, mock_logger):
    owner_id = 123
    release_id = 555
    release_name = "Test Release"
    main_artist_name = "Famous Artist"
    release_date = timezone.now().date() + timedelta(days=10)

    event_data = {
        "owner_id": owner_id,
        "release_id": release_id,
        "release_name": release_name,
        "main_primary_artist": main_artist_name,
        "release_date": release_date,
    }

    send_release_released(event_data)

    mock_track_data = {
        "release_id": release_id,
        "release_name": release_name,
        "main_primary_artist": main_artist_name,
        "release_date": release_date,
    }

    mock_track.assert_called_once_with(
        owner_id, "Release Released", properties=mock_track_data
    )
    mock_logger.assert_called_once()


@patch('amuse.vendor.segment.events.logger.info')
@patch("amuse.vendor.segment.events.track")
def test_send_release_delivered(mock_track, mock_logger):
    owner_id = 123
    release_id = 555
    release_name = "Test Release"
    main_artist_name = "Famous Artist"
    release_date = timezone.now().date() + timedelta(days=10)

    event_data = {
        "owner_id": owner_id,
        "release_id": release_id,
        "release_name": release_name,
        "main_primary_artist": main_artist_name,
        "release_date": release_date,
    }

    send_release_delivered(event_data)

    mock_track_data = {
        "release_id": release_id,
        "release_name": release_name,
        "main_primary_artist": main_artist_name,
        "release_date": release_date,
    }

    mock_track.assert_called_once_with(
        owner_id, "Release Delivered", properties=mock_track_data
    )
    mock_logger.assert_called_once()


@patch('amuse.vendor.segment.events.logger.info')
@patch("amuse.vendor.segment.events.track")
def test_send_release_undeliverable(mock_track, mock_logger):
    owner_id = 123
    release_id = 555
    release_name = "Test Release"
    main_artist_name = "Famous Artist"
    release_date = timezone.now().date() + timedelta(days=10)

    event_data = {
        "owner_id": owner_id,
        "release_id": release_id,
        "release_name": release_name,
        "main_primary_artist": main_artist_name,
        "release_date": release_date,
    }

    send_release_undeliverable(event_data)

    mock_track_data = {
        "release_id": release_id,
        "release_name": release_name,
        "main_primary_artist": main_artist_name,
        "release_date": release_date,
    }

    mock_track.assert_called_once_with(
        owner_id, "Release Undeliverable", properties=mock_track_data
    )
    mock_logger.assert_called_once()


@patch('amuse.vendor.segment.events.logger.info')
@patch("amuse.vendor.segment.events.track")
def test_send_account_delete(mock_track, mock_logger):
    user_id = 123
    data = {
        'user_email': 'john.doe234234@example.com',
        'user_first_name': 'John',
        'user_last_name': 'Doe',
        'delete_requested_at': datetime.now(),
    }

    user_requested_account_delete(user_id, data)

    mock_track.assert_called_once_with(user_id, "Account Delete", properties=data)
    mock_logger.assert_called_once()


@pytest.mark.django_db
@patch("amuse.vendor.segment.events.identify")
def test_identify(mock_identify):
    user = UserFactory()
    platform_name = 'web'

    identify_user(user, platform_name)

    mock_identify.assert_called_once()


@pytest.mark.django_db
@patch("amuse.vendor.segment.events.identify")
def test_identify_not_called_user_none(mock_identify):
    user = None
    platform_name = 'web'

    identify_user(user, platform_name)

    mock_identify.assert_not_called()


@pytest.mark.django_db
@patch("amuse.vendor.segment.events.track_sync")
@patch("amuse.vendor.segment.tasks.send_segment_track.delay")
def test_track(mock_async, mock_sync):
    from waffle.testutils import override_sample

    with override_sample(WAFFLE_SAMPLE_KEY, active=True):
        track(1, 'test_event')
        assert mock_async.call_count == 1
        assert mock_sync.call_count == 0

    mock_async.reset_mock()
    mock_sync.reset_mock()
    with override_sample(WAFFLE_SAMPLE_KEY, active=False):
        track(1, 'test_event')
        assert mock_async.call_count == 0
        assert mock_sync.call_count == 1


@pytest.mark.django_db
@patch("amuse.vendor.segment.events.identify_sync")
@patch("amuse.vendor.segment.tasks.send_segment_identify.delay")
def test_identify(mock_async, mock_sync):
    from waffle.testutils import override_sample

    with override_sample(WAFFLE_SAMPLE_KEY, active=True):
        identify(1, {})
        assert mock_async.call_count == 1
        assert mock_sync.call_count == 0

    mock_async.reset_mock()
    mock_sync.reset_mock()
    with override_sample(WAFFLE_SAMPLE_KEY, active=False):
        identify(1, {})
        assert mock_async.call_count == 0
        assert mock_sync.call_count == 1
