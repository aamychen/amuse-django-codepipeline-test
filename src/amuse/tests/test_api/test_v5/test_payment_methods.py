from unittest.mock import patch

import responses
from django.urls import reverse
from rest_framework import status

from amuse.tests.helpers import add_zendesk_mock_post_response
from amuse.tests.test_api.base import API_V5_ACCEPT_VALUE
from amuse.tests.test_api.base import AmuseAPITestCase
from amuse.tests.test_vendor.test_adyen.base import AdyenBaseTestCase
from amuse.tests.test_vendor.test_adyen.helpers import (
    mock_payment_details,
    mock_payment_methods,
)
from countries.tests.factories import CountryFactory
from subscriptions.models import Subscription
from subscriptions.tests.factories import SubscriptionFactory, SubscriptionPlanFactory
from users.tests.factories import UserFactory


class PaymentMethodsTest(AmuseAPITestCase):
    def setUp(self):
        super().setUp()
        self.country = CountryFactory(is_adyen_enabled=True)
        self.plan = SubscriptionPlanFactory(countries=[self.country])
        self.url = reverse('get-supported-payment-method')
        self.user = UserFactory()
        self.client.credentials(HTTP_ACCEPT=API_V5_ACCEPT_VALUE)
        self.client.force_authenticate(self.user)

    @patch('amuse.api.base.views.payment_methods.get_payment_methods')
    def test_valid_request_returns_adyen_response(self, mocked_payment_methods):
        adyen_response = mock_payment_methods()
        mocked_payment_methods.return_value = adyen_response
        data = {'country': self.country.code, 'subscription_plan': self.plan.pk}
        response = self.client.get(
            self.url, **self._as_query_string(data), format='json'
        )

        mocked_payment_methods.assert_called_with(
            self.plan,
            data['country'],
            4,
            localised=True,  # localised kwarg should be true on V5
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json(), adyen_response)

    def test_price_card_error_returns_400(self):
        plan = SubscriptionPlanFactory(create_card=False)
        data = {'country': self.country.code, 'subscription_plan': plan.pk}
        response = self.client.get(
            self.url, **self._as_query_string(data), format='json'
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(
            response.json(),
            [
                f'No PriceCard found for Plan {plan.name} (id={plan.pk}) and Country {self.country.code}'
            ],
        )


class UpdateSubscriptionPaymentMethodTestCase(AmuseAPITestCase, AdyenBaseTestCase):
    @responses.activate
    def setUp(self):
        add_zendesk_mock_post_response()
        self.country = CountryFactory(is_adyen_enabled=True)
        self.user = UserFactory()
        self.plan = SubscriptionPlanFactory(countries=[self.country])
        self.subscription = SubscriptionFactory(user=self.user, plan=self.plan)
        self.client.credentials(HTTP_ACCEPT=API_V5_ACCEPT_VALUE)
        self.client.force_authenticate(self.user)
        self.url = reverse('update-current-payment-method')

    @patch('amuse.api.v4.serializers.subscription.get_payment_country')
    @patch('amuse.api.base.views.payment_methods.authorise_payment_method')
    @patch('amuse.api.base.views.payment_methods.subscription_payment_method_changed')
    def test_returns_204(
        self, mocked_cio, mocked_authorise_payment_method, mocked_get_payment_country
    ):
        payment_details = mock_payment_details()
        payload = {'country': self.country.code, 'payment_details': payment_details}
        mocked_get_payment_country.return_value = self.country
        mocked_authorise_payment_method.return_value = {'is_success': True}

        response = self.client.put(self.url, payload, format='json')

        mocked_authorise_payment_method.assert_called_with(
            self.user,
            payload['payment_details']['paymentMethod'],
            self.country,
            4,
            '127.0.0.1',
            payload['payment_details'].get('browserInfo'),
            payload.get('return_url'),
            localised=True,
            billing_address=payment_details['billingAddress'],
        )
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        mocked_cio.assert_called_once_with(self.subscription, '', '127.0.0.1')


class AdyenSubscriptionsAllowedOnlyTestCase(AmuseAPITestCase):
    @responses.activate
    @patch('amuse.tasks.zendesk_create_or_update_user')
    def setUp(self, mock_zendesk):
        self.country = CountryFactory(is_adyen_enabled=True)
        self.user = UserFactory()
        self.plan = SubscriptionPlanFactory()
        self.client.force_authenticate(self.user)
        self.client.credentials(HTTP_ACCEPT=API_V5_ACCEPT_VALUE)

        self.expected_response = {'detail': 'Subscription Provider Mismatch Error'}
        self.non_adyen_providers = [
            provider
            for provider in Subscription.PROVIDER_CHOICES
            if provider[0] != Subscription.PROVIDER_ADYEN
        ]

    @responses.activate
    def test_non_adyen_update_is_forbidden(self):
        new_plan = SubscriptionPlanFactory()
        url = reverse('update-current-payment-method')

        for provider in self.non_adyen_providers:
            with self.subTest(
                msg=f'Update payment method provider="{provider[1]}" subscription'
            ):
                subscription = SubscriptionFactory(
                    user=self.user, plan=self.plan, provider=provider[0]
                )

                payload = {
                    'country': self.country.code,
                    'payment_details': mock_payment_details(),
                }
                response = self.client.put(url, payload, format='json')

                self.assertEqual(status.HTTP_400_BAD_REQUEST, response.status_code)
                self.assertEqual(self.expected_response, response.json())
