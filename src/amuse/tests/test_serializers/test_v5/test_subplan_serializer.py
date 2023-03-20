from datetime import timedelta
from decimal import Decimal
from unittest import mock

from django.contrib.auth.models import AnonymousUser
from django.test import TestCase, RequestFactory
from django.utils import timezone

from amuse.api.v5.serializers.subscription_plan import SubscriptionPlanSerializer
from countries.tests.factories import CountryFactory, CurrencyFactory
from subscriptions.models import Subscription
from subscriptions.tests.factories import (
    SubscriptionPlanFactory,
    IntroductoryPriceCardFactory,
    SubscriptionFactory,
)
from users.tests.factories import UserFactory


class TestSubPlanSerializer(TestCase):
    @mock.patch("amuse.tasks.zendesk_create_or_update_user")
    def setUp(self, mock_zendesk):
        self.subplan = SubscriptionPlanFactory()

        self.request = RequestFactory().get('/noop')
        self.request.user = AnonymousUser()
        self.context = {'request': self.request}

    @mock.patch("amuse.api.v5.serializers.subscription_plan.Common.get_country_code")
    def test_plan_has_tier(self, mocked_func):
        mocked_func.return_value = 'US'
        serialized_plan = SubscriptionPlanSerializer(
            self.subplan, context=self.context
        ).data
        assert serialized_plan["tier"] == 2


class TestSubscriptionPlanIntroductoryPriceAnonymousSerializer(TestCase):
    @mock.patch("amuse.tasks.zendesk_create_or_update_user")
    def setUp(self, mock_zendesk):
        self.subplan = SubscriptionPlanFactory()

        self.request = RequestFactory().get('/noop')
        self.request.user = AnonymousUser()
        self.context = {'request': self.request, 'country': 'US'}

    def test_is_null_if_no_intro_price(self):
        serialized_plan = SubscriptionPlanSerializer(
            self.subplan, context=self.context
        ).data
        self.assertIn('introductory_price', serialized_plan)
        self.assertIsNone(serialized_plan["introductory_price"])

    def test_is_null_if_intro_price_is_not_active(self):
        two_days_ago = timezone.now().date() - timedelta(days=2)
        one_day_ago = timezone.now().date() - timedelta(days=1)

        country = CountryFactory(code='US')
        currency = CurrencyFactory(code='USD')
        introductory_card = IntroductoryPriceCardFactory(
            plan=self.subplan,
            price=Decimal('1.23'),
            currency=currency,
            countries=[country],
            start_date=two_days_ago,
            end_date=one_day_ago,
        )

        serialized_plan = SubscriptionPlanSerializer(
            self.subplan, context=self.context
        ).data
        self.assertIn('introductory_price', serialized_plan)
        self.assertIsNone(serialized_plan["introductory_price"])

        def test_is_not_null_if_user_is_anonymous(self):
            country = CountryFactory(code='US')
            currency = CurrencyFactory(code='USD')
            introductory_card = IntroductoryPriceCardFactory(
                plan=self.subplan,
                price=Decimal('1.23'),
                currency=currency,
                countries=[country],
            )

            serialized_plan = SubscriptionPlanSerializer(
                self.subplan, context=self.context
            ).data
            self.assertIn('introductory_price', serialized_plan)
            self.assertIsNotNone(serialized_plan["introductory_price"])


class TestSubscriptionPlanIntroductoryPriceSerializer(TestCase):
    @mock.patch("amuse.tasks.zendesk_create_or_update_user")
    def setUp(self, mock_zendesk):
        self.subplan = SubscriptionPlanFactory()
        self.request = RequestFactory().get('/noop')
        self.request.user = UserFactory()
        self.context = {'request': self.request, 'country': 'US'}

    def test_is_null_if_user_not_eligible_for_intro(self):
        SubscriptionFactory(user=self.request.user)
        country = CountryFactory(code='US')
        currency = CurrencyFactory(code='USD')
        introductory_card = IntroductoryPriceCardFactory(
            plan=self.subplan,
            price=Decimal('1.23'),
            currency=currency,
            countries=[country],
        )

        serialized_plan = SubscriptionPlanSerializer(
            self.subplan, context=self.context
        ).data
        self.assertIn('introductory_price', serialized_plan)
        self.assertIsNone(serialized_plan["introductory_price"])

    def test_is_not_null_if_is_eligible_for_intro(self):
        SubscriptionFactory(user=self.request.user, status=Subscription.STATUS_CREATED)
        country = CountryFactory(code='US')
        currency = CurrencyFactory(code='USD')
        introductory_card = IntroductoryPriceCardFactory(
            plan=self.subplan,
            price=Decimal('1.23'),
            currency=currency,
            countries=[country],
        )

        serialized_plan = SubscriptionPlanSerializer(
            self.subplan, context=self.context
        ).data
        self.assertIn('introductory_price', serialized_plan)
        self.assertIsNotNone(serialized_plan["introductory_price"])

    @mock.patch("amuse.api.v5.serializers.subscription_plan.Common.get_country_code")
    def test_introductory_price_fields(self, mocked_func):
        mocked_func.return_value = 'US'
        country = CountryFactory(code='US')
        currency = CurrencyFactory(code='USD')
        introductory_card = IntroductoryPriceCardFactory(
            plan=self.subplan,
            price=Decimal('1.23'),
            currency=currency,
            countries=[country],
        )

        serialized_plan = SubscriptionPlanSerializer(
            self.subplan, context=self.context
        ).data

        introductory_price = serialized_plan["introductory_price"]
        self.assertIsNotNone(introductory_price)

        expected = dict(
            introductory_price,
            **{
                'introductory_price_id': introductory_card.pk,
                'price': '1.23',
                'period': introductory_card.period,
                'price_display': 'USD 1.23',
                'currency': 'USD',
            },
        )
        self.assertEqual(expected, introductory_price)
