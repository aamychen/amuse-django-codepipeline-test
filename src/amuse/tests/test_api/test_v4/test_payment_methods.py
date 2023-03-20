from datetime import datetime, timedelta
from unittest.mock import patch

import responses
from dateutil.relativedelta import relativedelta
from django.urls import reverse
from django.utils import timezone
from rest_framework import status

from amuse.tests.helpers import add_zendesk_mock_post_response
from amuse.tests.test_api.base import (
    API_V2_ACCEPT_VALUE,
    API_V4_ACCEPT_VALUE,
    AmuseAPITestCase,
)
from amuse.tests.test_vendor.test_adyen.base import AdyenBaseTestCase
from amuse.tests.test_vendor.test_adyen.helpers import (
    mock_payment_details,
    mock_payment_methods,
)
from amuse.vendor.adyen.helpers import convert_to_end_of_the_day
from countries.tests.factories import CountryFactory
from payments.models import PaymentTransaction
from payments.tests.factories import PaymentTransactionFactory
from subscriptions.models import Subscription
from subscriptions.tests.factories import SubscriptionFactory, SubscriptionPlanFactory
from users.tests.factories import UserFactory, UserMetadataFactory


class PaymentMethodsTest(AmuseAPITestCase):
    def setUp(self):
        super().setUp()
        self.country = CountryFactory(is_adyen_enabled=True)
        self.plan = SubscriptionPlanFactory()
        self.url = reverse('get-supported-payment-method')
        self.user = UserFactory()
        self.client.credentials(HTTP_ACCEPT=API_V4_ACCEPT_VALUE)
        self.client.force_authenticate(self.user)

    def test_invalid_request_returns_400(self):
        response = self.client.get(self.url, {})
        payload = response.json()
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(payload['country'][0], 'This field is required.')
        self.assertEqual(payload['subscription_plan'][0], 'This field is required.')

    @patch('amuse.api.base.views.payment_methods.get_payment_methods')
    def test_valid_request_returns_adyen_response(self, mocked_payment_methods):
        adyen_response = mock_payment_methods()
        mocked_payment_methods.return_value = adyen_response
        data = {'country': self.country.code, 'subscription_plan': self.plan.pk}
        response = self.client.get(
            self.url, **self._as_query_string(data), format='json'
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json(), adyen_response)

    def test_permissions(self):
        self.client.logout()
        self.assertEqual(
            self.client.get(self.url).status_code, status.HTTP_401_UNAUTHORIZED
        )

    def test_wrong_api_version_return_400(self):
        self.client.credentials(HTTP_ACCEPT=API_V2_ACCEPT_VALUE)

        response = self.client.post(self.url, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.json(), {'detail': 'API version is not supported.'})


class UpdateSubscriptionPaymentMethodTestCase(AmuseAPITestCase, AdyenBaseTestCase):
    @responses.activate
    def setUp(self):
        add_zendesk_mock_post_response()
        self.country = CountryFactory(is_adyen_enabled=True)
        self.user = UserFactory()
        self.subscription = SubscriptionFactory(user=self.user)
        self.client.credentials(HTTP_ACCEPT=API_V4_ACCEPT_VALUE)
        self.client.force_authenticate(self.user)
        self.url = reverse('update-current-payment-method')

    def test_unsupported_api_version_returns_error(self):
        self.client.credentials(HTTP_ACCEPT=API_V2_ACCEPT_VALUE)
        response = self.client.put(self.url, {}, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.json(), {'detail': 'API version is not supported.'})

    def test_returns_400_when_missing_data(self):
        response = self.client.put(self.url, {}, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        expected_message = {
            'country': ['This field is required.'],
            'payment_details': ['This field is required.'],
        }

        self.assertEqual(response.json(), expected_message)
        self.assertEqual(self.user.current_subscription(), self.subscription)

    @patch('amuse.api.v4.serializers.subscription.get_payment_country')
    @patch('amuse.api.base.views.payment_methods.authorise_payment_method')
    @patch('amuse.api.base.views.payment_methods.subscription_payment_method_changed')
    def test_returns_204(
        self, mocked_cio, mocked_authorise_payment_method, mocked_get_payment_country
    ):
        payload = {
            'country': self.country.code,
            'payment_details': mock_payment_details(),
        }
        mocked_get_payment_country.return_value = self.country
        mocked_authorise_payment_method.return_value = {'is_success': True}

        response = self.client.put(self.url, payload, format='json')

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        mocked_cio.assert_called_once_with(self.subscription, '', '127.0.0.1')

    @patch('amuse.api.v4.serializers.subscription.get_payment_country')
    @patch('amuse.api.base.views.payment_methods.authorise_payment_method')
    def test_returns_200_when_3ds_mandated(
        self, mocked_authorise_payment_method, mocked_get_payment_country
    ):
        payload = {
            'country': self.country.code,
            'payment_details': mock_payment_details(),
        }
        mocked_get_payment_country.return_value = self.country
        expected_response = {'is_success': False, 'action': {}}
        mocked_authorise_payment_method.return_value = expected_response

        response = self.client.put(self.url, payload, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data, expected_response)

    @responses.activate
    @patch('amuse.api.v4.serializers.subscription.get_payment_country')
    @patch('amuse.api.base.views.payment_methods.authorise_payment_method')
    def test_returns_500_when_error_raised(
        self, mocked_authorise_payment_method, mocked_get_payment_country
    ):
        payload = {
            'country': self.country.code,
            'payment_details': mock_payment_details(),
        }
        mocked_get_payment_country.return_value = self.country
        expected_response = {'is_success': False, 'error_message': 'some error'}
        mocked_authorise_payment_method.return_value = expected_response

        response = self.client.put(self.url, payload, format='json')

        self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
        self.assertEqual(response.data, expected_response)


class AdyenSubscriptionsAllowedOnlyTestCase(AmuseAPITestCase):
    @responses.activate
    @patch('amuse.tasks.zendesk_create_or_update_user')
    def setUp(self, mock_zendesk):
        self.country = CountryFactory(is_adyen_enabled=True)
        self.user = UserFactory()
        self.plan = SubscriptionPlanFactory()
        self.client.force_authenticate(self.user)
        self.client.credentials(HTTP_ACCEPT=API_V4_ACCEPT_VALUE)

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
