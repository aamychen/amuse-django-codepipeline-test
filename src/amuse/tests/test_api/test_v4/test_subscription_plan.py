from decimal import Decimal
from unittest.mock import patch

from django.urls import reverse
from rest_framework import status

from amuse.tests.test_api.base import (
    API_V2_ACCEPT_VALUE,
    API_V4_ACCEPT_VALUE,
    AmuseAPITestCase,
)
from countries.tests.factories import CountryFactory
from subscriptions.tests.factories import SubscriptionPlanFactory
from users.tests.factories import UserFactory


class SubscriptionPlanTestCase(AmuseAPITestCase):
    def setUp(self):
        self.default_country = CountryFactory(code='US')
        self.hidden_plan = SubscriptionPlanFactory(
            is_public=False, countries=[self.default_country]
        )
        self.plan = SubscriptionPlanFactory(
            price=Decimal("20.00"),
            period=1,
            apple_product_id='trial',
            apple_product_id_notrial='notrial',
            countries=[self.default_country],
        )
        self.url = reverse('subscription-plans')
        self.client.credentials(HTTP_ACCEPT=API_V4_ACCEPT_VALUE)

    def test_all_fields_returned_for_non_logged_in_user(self):
        response = self.client.get(self.url)
        response_json = response.json()

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response_json), 1)
        self.assertEqual(response_json[0]['name'], self.plan.name)
        self.assertEqual(response_json[0]['id'], self.plan.pk)
        self.assertEqual(
            response_json[0]['apple_product_id'], self.plan.apple_product_id
        )
        self.assertEqual(response_json[0]['best_deal'], True)

    @patch('amuse.tasks.zendesk_create_or_update_user')
    def test_apple_product_id_no_trial_available(self, mock_zendesk):
        user = UserFactory(is_pro=True)
        self.client.force_authenticate(user)

        response = self.client.get(self.url)
        response_json = response.json()

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            response_json[0]['apple_product_id'], self.plan.apple_product_id_notrial
        )

    def test_wrong_api_version_return_400(self):
        self.client.credentials(HTTP_ACCEPT=API_V2_ACCEPT_VALUE)

        response = self.client.post(self.url, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.json(), {'detail': 'API version is not supported.'})

    def test_best_deals_are_correct(self):
        best_plan = SubscriptionPlanFactory(
            name="12 months",
            price=Decimal("100.00"),
            period=12,
            countries=[self.default_country],
        )
        plan = SubscriptionPlanFactory(
            name="6 months",
            price=Decimal("60.00"),
            period=6,
            countries=[self.default_country],
        )

        response = self.client.get(self.url)
        response_json = response.json()

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response_json), 3)

        best_deal_plan_list = [p for p in response_json if p["best_deal"]]
        self.assertEqual(len(best_deal_plan_list), 1)

        best_deal_plan = best_deal_plan_list[0]
        self.assertEqual(best_deal_plan["name"], best_plan.name)

        response_json.remove(best_deal_plan)
        self.assertFalse(response_json[0]["best_deal"])
        self.assertFalse(response_json[1]["best_deal"])
