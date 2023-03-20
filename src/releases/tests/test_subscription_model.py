from datetime import timedelta

import responses
from django.test import TestCase, override_settings
from django.utils import timezone

from amuse.tests.helpers import (
    add_zendesk_mock_post_response,
    ZENDESK_MOCK_API_URL_TOKEN,
)
from subscriptions.models import Subscription
from subscriptions.tests.factories import SubscriptionFactory, SubscriptionPlanFactory
from users.models import UserArtistRole
from users.tests.factories import UserFactory, Artistv2Factory, UserArtistRoleFactory


@override_settings(**ZENDESK_MOCK_API_URL_TOKEN)
class SubscriptionTestCase(TestCase):
    @responses.activate
    def setUp(self):
        add_zendesk_mock_post_response()
        self.plan = SubscriptionPlanFactory(trial_days=90, period=12)

        self.user = UserFactory()
        self.subscription = SubscriptionFactory(
            plan=self.plan, provider=Subscription.PROVIDER_ADYEN, user=self.user
        )

        self.artist1 = Artistv2Factory()
        self.artist2 = Artistv2Factory()

        # Users #1,2 belong to the team of artist #2
        UserArtistRoleFactory(user=self.user, artist=self.artist1)
        UserArtistRoleFactory(
            user=self.user, artist=self.artist2, main_artist_profile=True
        )

    def test_main_primary_artist_reseted_if_subscription_status_changed_to_actice(self):
        qs = UserArtistRole.objects.filter(user=self.user, main_artist_profile=True)

        self.assertTrue(qs.exists(), 'There should be one main primary artist')

        self.subscription.status = Subscription.STATUS_ERROR
        self.subscription.save()
        self.assertTrue(qs.exists(), 'There should be one main primary artist')

        self.subscription.status = Subscription.STATUS_ACTIVE
        self.subscription.save()
        self.assertFalse(qs.exists(), 'There should be none main primary artist')


@override_settings(**ZENDESK_MOCK_API_URL_TOKEN)
class SubscriptionIsFreeTrialActiveTestCase(TestCase):
    @responses.activate
    def setUp(self):
        add_zendesk_mock_post_response()
        self.plan = SubscriptionPlanFactory()

        self.user = UserFactory()
        self.subscription = SubscriptionFactory(
            plan=self.plan, provider=Subscription.PROVIDER_GOOGLE, user=self.user
        )

    def test_for_specific_subscription_status(self):
        self.subscription.free_trial_from = timezone.now() - timedelta(days=5)
        self.subscription.free_trial_until = timezone.now() + timedelta(days=5)
        expected_to_be_active = [
            Subscription.STATUS_ACTIVE,
            Subscription.STATUS_GRACE_PERIOD,
        ]

        for status_choice in Subscription.STATUS_CHOICES:
            status = status_choice[0]
            with self.subTest(
                msg=f'Checking if subscription free trial is active for status "{status}"'
            ):
                self.subscription.status = status

                expected = status in expected_to_be_active
                actual = self.subscription.is_free_trial_active()
                self.assertEqual(
                    expected, actual, f'Status {status} expected {expected}'
                )

    def test_based_on_free_trial_period(self):
        test_cases = [
            {
                'description': 'free_trial_from not set, free_trial_is_active must be False',
                'free_trial_from': None,
                'free_trial_until': timezone.now() + timedelta(days=5),
                'expected': False,
            },
            {
                'description': 'free_trial_until not set, free_trial_is_active must be False',
                'free_trial_from': timezone.now() - timedelta(days=5),
                'free_trial_until': None,
                'expected': False,
            },
            {
                'description': 'now() is before free trial period, free_trial_is_active must be False',
                'free_trial_from': timezone.now() - timedelta(days=5),
                'free_trial_until': timezone.now() - timedelta(days=2),
                'expected': False,
            },
            {
                'description': 'now() is after free trial period, free_trial_is_active must be False',
                'free_trial_from': timezone.now() + timedelta(days=5),
                'free_trial_until': timezone.now() + timedelta(days=10),
                'expected': False,
            },
            {
                'description': 'now() is inside free trial period, free_trial_is_active must be True',
                'free_trial_from': timezone.now() - timedelta(days=5),
                'free_trial_until': timezone.now() + timedelta(days=2),
                'expected': True,
            },
        ]

        self.subscription.status = Subscription.STATUS_ACTIVE
        for test_case in test_cases:
            with self.subTest(msg=f'{test_case["description"]}'):
                self.subscription.free_trial_from = test_case['free_trial_from']
                self.subscription.free_trial_until = test_case['free_trial_until']

                expected = test_case['expected']
                actual = self.subscription.is_free_trial_active()
                self.assertEqual(expected, actual, test_case['description'])
