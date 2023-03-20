from datetime import timedelta
from decimal import Decimal
from unittest import mock

import responses
from django.urls import reverse
from django.utils import timezone
from rest_framework import status

from amuse.tests.helpers import add_zendesk_mock_post_response
from amuse.tests.test_api.base import AmuseAPITestCase, API_V5_ACCEPT_VALUE
from countries.tests.factories import CountryFactory, CurrencyFactory
from payments.tests.factories import PaymentTransactionFactory
from subscriptions.models import Subscription
from subscriptions.tests.factories import (
    SubscriptionPlanFactory,
    PriceCardFactory,
    SubscriptionFactory,
    IntroductoryPriceCardFactory,
)
from users.tests.factories import UserFactory


class SubscriptionPlanTestCase(AmuseAPITestCase):
    def setUp(self):
        self.default_country = CountryFactory(code='US')
        self.currency = CurrencyFactory(code='USD')
        self.hidden_plan = SubscriptionPlanFactory(
            is_public=False, countries=[self.default_country]
        )
        self.plan = SubscriptionPlanFactory(
            period=1,
            apple_product_id='trial',
            apple_product_id_notrial='notrial',
            create_card=False,
        )
        self.card = PriceCardFactory(
            price=Decimal("20.00"),
            plan=self.plan,
            currency=self.currency,
            countries=[self.default_country],
        )
        self.url = reverse('subscription-plans')
        self.client.credentials(HTTP_ACCEPT=API_V5_ACCEPT_VALUE)

    def test_localized_fields_returned(self):
        response = self.client.get(self.url)
        plan = response.data[0]
        self.assertEqual(plan['id'], self.plan.id)
        self.assertEqual(plan['name'], self.plan.name)
        self.assertEqual(plan['price'], str(self.card.price))
        self.assertEqual(plan['period_price'], str(self.card.period_price))
        self.assertEqual(plan['price_display'], 'USD 20')
        self.assertEqual(plan['period_price_display'], 'USD 20')
        self.assertEqual(plan['currency'], self.card.currency.code)
        self.assertEqual(plan['period'], self.plan.period)
        self.assertEqual(plan['trial_days'], self.plan.trial_days)
        self.assertEqual(plan['apple_product_id'], self.plan.apple_product_id)
        self.assertEqual(plan['country'], self.default_country.code)

    def test_formatting(self):
        se = CountryFactory(code='SE')
        currency = CurrencyFactory(code='SEK')
        plan = SubscriptionPlanFactory(period=12, create_card=False)
        card = PriceCardFactory(
            price=Decimal("559.00"), plan=plan, currency=currency, countries=[se]
        )

        response = self.client.get(self.url, {'country': 'SE'})
        plan = response.data[0]
        self.assertEqual(plan['period_price'], '46.58')
        self.assertEqual(plan['price_display'], 'SEK 559')
        self.assertEqual(plan['period_price_display'], 'SEK 46.58')
        self.assertEqual(plan['country'], se.code)

    def test_filtering_by_country_provided(self):
        es = CountryFactory(code='ES')
        card = PriceCardFactory(plan=self.plan, countries=[es])

        response = self.client.get(self.url, {'country': 'ES'})
        response_json = response.json()

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response_json), 1)
        self.assertEqual(response_json[0]['name'], self.plan.name)
        self.assertEqual(response_json[0]['price'], str(card.price))
        self.assertEqual(response_json[0]['currency'], card.currency.code)
        self.assertEqual(response_json[0]['country'], es.code)

    def test_filtering_by_ip_detected(self):
        es = CountryFactory(code='ES')
        card = PriceCardFactory(countries=[es])

        response = self.client.get(self.url, HTTP_CF_IPCOUNTRY='ES')
        response_json = response.json()

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response_json), 1)
        self.assertEqual(response_json[0]['name'], card.plan.name)
        self.assertEqual(response_json[0]['price'], str(card.price))
        self.assertEqual(response_json[0]['currency'], card.currency.code)
        self.assertEqual(response_json[0]['country'], es.code)

    def test_filtering_by_country_has_priority(self):
        es = CountryFactory(code='ES')
        card1 = PriceCardFactory(plan=self.plan, countries=[es])

        se = CountryFactory(code='SE')
        card2 = PriceCardFactory(plan=self.plan, countries=[se])

        response = self.client.get(self.url, {'country': 'ES'}, HTTP_CF_IPCOUNTRY='SE')
        response_json = response.json()

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response_json), 1)
        self.assertEqual(response_json[0]['name'], self.plan.name)
        self.assertEqual(response_json[0]['price'], str(card1.price))
        self.assertEqual(response_json[0]['currency'], card1.currency.code)
        self.assertEqual(response_json[0]['country'], es.code)

    def test_filtering_invalid_country(self):
        country_id = 'NO'
        response = self.client.get(self.url, {'country': country_id})

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.json(), ['Invalid Country: NO'])

    def test_plans_without_card_for_country_provided_are_hidden(self):
        plan = SubscriptionPlanFactory(create_card=False)

        response = self.client.get(self.url)
        response_json = response.json()

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response_json), 1)
        self.assertEqual(response_json[0]['name'], self.plan.name)

    def test_plans_with_multiple_cards_for_country_provided_throw_error(self):
        card = PriceCardFactory(plan=self.plan, countries=[self.default_country])

        response = self.client.get(self.url)
        response_json = response.json()

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(len(response_json), 1)
        self.assertEqual(
            response_json[0],
            f'More than one PriceCard found for Plan {self.plan.name} '
            f'(id={self.plan.pk}) and Country {self.default_country.code}',
        )

    def test_us_plans_are_returned_as_default(self):
        country = CountryFactory(code='AU')
        response = self.client.get(self.url, {'country': country.code})
        response_json = response.json()

        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertEqual(len(response_json), 1)
        self.assertEqual(response_json[0]['name'], self.plan.name)
        self.assertEqual(response_json[0]['price'], str(self.card.price))
        self.assertEqual(response_json[0]['currency'], 'USD')
        self.assertEqual(response_json[0]['country'], country.code)

    def test_fetched_card_is_price_card_and_it_is_not_introductory_price_card(self):
        introductory_card = IntroductoryPriceCardFactory(
            plan=self.plan, countries=[self.default_country]
        )

        actual1 = self.plan.get_price_card()
        self.assertEqual(self.card.pk, actual1.pk)
        self.assertEqual(1, self.plan.pricecard_set.count())

    def test_fallback_to_price_card_if_introductory_price_card_missing(self):
        actual2 = self.plan.get_price_card(use_intro_price=True)
        self.assertEqual(self.card.pk, actual2.pk)

    def test_get_introductory_price_card(self):
        introductory_card = IntroductoryPriceCardFactory(
            plan=self.plan, countries=[self.default_country]
        )

        actual2 = self.plan.get_price_card(use_intro_price=True)
        self.assertEqual(introductory_card.pk, actual2.pk)

        actual3 = self.plan.get_introductory_price_card(
            country_code=self.default_country.code
        )
        self.assertEqual(introductory_card.pk, actual3.pk)

    @mock.patch('subscriptions.models.logger.error')
    def test_fallback_if_multiple_introductory_price_cards(self, mock_error):
        country = CountryFactory(code='xy')
        introductory_card = IntroductoryPriceCardFactory(
            plan=self.plan, countries=[country]
        )
        introductory_card = IntroductoryPriceCardFactory(
            plan=self.plan, countries=[country]
        )

        actual = self.plan.get_introductory_price_card('xy')
        self.assertIsNone(actual)
        mock_error.assert_called_once()


class CurrentSubscriptionPlanGoogleFreeTrial(AmuseAPITestCase):
    @responses.activate
    def setUp(self):
        add_zendesk_mock_post_response()
        self.currency = CurrencyFactory(code='USD')
        self.country = CountryFactory(code='US')
        self.user = UserFactory()

        self.plan = SubscriptionPlanFactory(
            period=1,
            google_product_id='NOTRIAL',
            google_product_id_trial='TRIAL',
            google_product_id_introductory='INTRO',
            create_card=False,
        )
        self.card = PriceCardFactory(
            price=Decimal("20.00"),
            plan=self.plan,
            currency=self.currency,
            countries=[self.country],
        )

        self.client.force_authenticate(self.user)
        self.client.credentials(HTTP_ACCEPT=API_V5_ACCEPT_VALUE)
        self.url = reverse('subscription-list')

    def test_user_has_free_trial_currently(self):
        SubscriptionFactory(
            user=self.user,
            plan=self.plan,
            status=Subscription.STATUS_ACTIVE,
            free_trial_from=timezone.now() - timedelta(days=5),
            free_trial_until=timezone.now() + timedelta(days=5),
        )

        response = self.client.get(path=self.url, format='json')
        data = response.data

        self.assertEqual(
            self.plan.google_product_id_trial,
            data['current_plan']['google_product_id'],
            'User has active free-trial subscription',
        )
        self.assertEqual(
            self.plan.google_product_id_trial,
            data['plan']['google_product_id'],
            'Next plan is same as current plan (Amuse is not aware of Google subscription upgrade/downgrade)',
        )

    def test_user_has_active_subscription_currently(self):
        SubscriptionFactory(
            user=self.user, plan=self.plan, status=Subscription.STATUS_ACTIVE
        )

        response = self.client.get(path=self.url, format='json')
        data = response.data

        self.assertEqual(
            self.plan.google_product_id,
            data['current_plan']['google_product_id'],
            'User has active NOTRIAL subscription',
        )
        self.assertEqual(
            self.plan.google_product_id,
            data['plan']['google_product_id'],
            'Next plan is same as current plan (Amuse is not aware of Google subscription upgrade/downgrade)',
        )

    def test_user_has_active_introductory_subscription_currently(self):
        sub = SubscriptionFactory(
            user=self.user,
            plan=self.plan,
            status=Subscription.STATUS_ACTIVE,
            provider=Subscription.PROVIDER_GOOGLE,
        )
        PaymentTransactionFactory(
            plan=self.plan,
            subscription=sub,
            user=self.user,
            customer_payment_payload={
                'google_subscription_id': self.plan.google_product_id_introductory
            },
        )

        response = self.client.get(path=self.url, format='json')
        data = response.data

        self.assertEqual(
            self.plan.google_product_id_introductory,
            data['current_plan']['google_product_id'],
            'User has active INTRO subscription',
        )
        self.assertEqual(
            self.plan.google_product_id_introductory,
            data['plan']['google_product_id'],
            'Next plan is same as current plan (Amuse is not aware of Google subscription upgrade/downgrade)',
        )

    def test_return_default_google_product_id(self):
        sub = SubscriptionFactory(
            user=self.user,
            plan=self.plan,
            status=Subscription.STATUS_ACTIVE,
            provider=Subscription.PROVIDER_GOOGLE,
        )

        response = self.client.get(path=self.url, format='json')
        data = response.data

        self.assertEqual(
            self.plan.google_product_id,
            data['current_plan']['google_product_id'],
            'User has active NOTRIAL subscription',
        )
        self.assertEqual(
            self.plan.google_product_id,
            data['plan']['google_product_id'],
            'Next plan is same as current plan (Amuse is not aware of Google subscription upgrade/downgrade)',
        )
