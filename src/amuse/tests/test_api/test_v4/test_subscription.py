import json
from datetime import timedelta
from unittest.mock import patch

import responses
from django.urls import reverse
from django.utils import timezone
from rest_framework import status

from amuse.platform import PlatformType
from amuse.settings.constants import NONLOCALIZED_PAYMENTS_COUNTRY
from amuse.tests.helpers import add_zendesk_mock_post_response
from amuse.tests.test_api.base import (
    API_V2_ACCEPT_VALUE,
    API_V4_ACCEPT_VALUE,
    AmuseAPITestCase,
)
from amuse.tests.test_vendor.test_adyen.base import AdyenBaseTestCase
from amuse.tests.test_vendor.test_adyen.helpers import (
    mock_country_check_expired_payment_details,
    mock_country_check_unsupported_payment_details,
    mock_payment_details,
)
from countries.tests.factories import CountryFactory
from payments.models import PaymentTransaction
from payments.tests.factories import PaymentTransactionFactory
from subscriptions.models import Subscription, SubscriptionPlan, SubscriptionPlanChanges
from subscriptions.tests.factories import SubscriptionFactory, SubscriptionPlanFactory
from users.tests.factories import UserFactory, UserMetadataFactory


class CreateSubscriptionTestCase(AmuseAPITestCase, AdyenBaseTestCase):
    @responses.activate
    def setUp(self):
        add_zendesk_mock_post_response()
        self.country = CountryFactory(is_adyen_enabled=True)
        self.user = UserFactory()
        self.plan = SubscriptionPlanFactory()
        self.client.force_authenticate(self.user)
        self.client.credentials(HTTP_ACCEPT=API_V4_ACCEPT_VALUE)
        self.url = reverse('create-adyen-subscription')

    @responses.activate
    @patch('amuse.api.base.views.subscription.subscription.subscription_new_started')
    def test_create_subscription_is_successful(self, mocked_segment):
        self._add_country_check_response(self.country.code)
        self._add_checkout_response('Authorised')
        country = self.country.code
        plan = self.plan.pk
        payment_details = mock_payment_details()

        headers = {'HTTP_USER_AGENT': 'amuse-android/3.4.41; WiFi'}
        response = self.client.post(
            self.url,
            {'country': country, 'plan': plan, 'payment_details': payment_details},
            format='json',
            **headers,
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(response.data['is_success'], response.data)
        mocked_segment.assert_called_once_with(
            self.user.current_subscription(),
            PlatformType.ANDROID,
            'amuse-android/3.4.41; WiFi',
            '127.0.0.1',
            NONLOCALIZED_PAYMENTS_COUNTRY,
        )
        self.assertEqual(
            self.user.current_subscription().latest_payment().category,
            PaymentTransaction.CATEGORY_INITIAL,
        )

        self.assertEqual(
            self.user.current_subscription().latest_payment().platform,
            PaymentTransaction.PLATFORM_ANDROID,
        )

    @responses.activate
    def test_create_subscription_refused(self):
        self._add_country_check_response(self.country.code)
        self._add_checkout_response('Refused')

        response = self.client.post(
            self.url,
            {
                'country': self.country.code,
                'plan': self.plan.pk,
                'payment_details': mock_payment_details(),
            },
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(response.json()['is_success'])
        self.assertIsNone(self.user.current_subscription())

    @responses.activate
    def test_create_subscription_returns_400_when_missing_data(self):
        response = self.client.post(self.url, {'plan': self.plan.pk}, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        expected_message = {
            'country': ['This field is required.'],
            'payment_details': ['This field is required.'],
        }

        self.assertEqual(response.json(), expected_message)
        self.assertIsNone(self.user.current_subscription())

    @responses.activate
    def test_create_subscription_returns_401_for_anonymous_user(self):
        self.client.logout()
        response = self.client.post(self.url)

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    @responses.activate
    def test_create_subscription_returns_403_for_already_pro_user(self):
        # Creating a subscription for the user will make it a pro user.
        SubscriptionFactory(user=self.user, plan=self.plan)

        response = self.client.post(self.url)

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    @responses.activate
    def test_create_subscription_returns_403_for_frozen_user(self):
        # make our user is free user
        self.user.subscriptions.all().delete()
        # Freeze user
        self.user.is_frozen = True
        self.user.save()
        self.user.refresh_from_db()

        # Creating a subscription for the user will make it a pro user.
        SubscriptionFactory(user=self.user, plan=self.plan)

        response = self.client.post(self.url)

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    @responses.activate
    @patch('amuse.vendor.adyen.logger.error')
    @patch('amuse.vendor.adyen.logger.info')
    @patch('amuse.vendor.adyen.logger.warning')
    def test_adyen_unsupported_payment_details_logs_warning(
        self, mock_warning_logger, mock_info_logger, mock_error_logger
    ):
        self._add_country_check_response(
            response=json.dumps(mock_country_check_unsupported_payment_details()),
            status_code=500,
        )

        response = self.client.post(
            self.url,
            {
                'country': self.country.code,
                'plan': self.plan.pk,
                'payment_details': mock_payment_details(),
            },
            format='json',
        )
        payload = response.json()

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(payload['country'][0], 'Payment country lookup failed')
        self.assertEqual(mock_info_logger.call_count, 2)
        mock_error_logger.assert_not_called()
        mock_warning_logger.assert_called_once()

    @responses.activate
    @patch('amuse.vendor.adyen.logger.error')
    @patch('amuse.vendor.adyen.logger.info')
    @patch('amuse.vendor.adyen.logger.warning')
    def test_adyen_invalid_payment_details_logs_on_info_level(
        self, mock_warning_logger, mock_info_logger, mock_error_logger
    ):
        self._add_country_check_response(
            response=json.dumps(mock_country_check_expired_payment_details()),
            status_code=422,
        )

        response = self.client.post(
            self.url,
            {
                'country': self.country.code,
                'plan': self.plan.pk,
                'payment_details': mock_payment_details(),
            },
            format='json',
        )
        payload = response.json()

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(payload['country'][0], 'Payment country lookup failed')
        self.assertEqual(mock_info_logger.call_count, 3)
        mock_error_logger.assert_not_called()
        mock_warning_logger.assert_not_called()


class SubscriptionPermissionTestCase(AmuseAPITestCase):
    def test_permissions(self):
        self.assertEqual(
            self.client.get(reverse('subscription-list')).status_code,
            status.HTTP_401_UNAUTHORIZED,
        )

    def test_wrong_api_version_return_400(self):
        user = UserFactory()
        self.client.credentials(HTTP_ACCEPT=API_V2_ACCEPT_VALUE)
        self.client.force_authenticate(user)
        urls = (
            reverse('create-adyen-subscription'),
            reverse('create-apple-subscription'),
            reverse('apple-subscription-info'),
            reverse('subscription-list'),
            reverse('update-current-subscription-plan'),
        )

        for url in urls:
            response = self.client.post(url, format='json')

            self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
            self.assertEqual(
                response.json(), {'detail': 'API version is not supported.'}
            )


class ActiveSubscriptionTestCase(AmuseAPITestCase, AdyenBaseTestCase):
    @responses.activate
    def setUp(self):
        self.plan = SubscriptionPlanFactory(trial_days=0)
        self.subscription = SubscriptionFactory(plan=self.plan)
        self.payment = PaymentTransactionFactory(
            subscription=self.subscription, user=self.subscription.user
        )
        self.url = reverse('subscription-list')
        self.client.force_authenticate(self.subscription.user)
        self.client.credentials(HTTP_ACCEPT=API_V4_ACCEPT_VALUE)

    def test_list(self):
        payload = self.client.get(self.url).json()

        self.assertEqual(
            payload['paid_until'], self.subscription.paid_until.isoformat()
        )
        self.assertEqual(payload['plan']['id'], self.subscription.plan_id)
        assert (
            payload['provider'] == self.payment.provider == self.subscription.provider
        )
        self.assertEqual(
            payload['valid_from'], self.subscription.valid_from.isoformat()
        )
        self.assertEqual(payload['plan']['id'], self.plan.pk)
        self.assertEqual(payload['current_plan']['id'], self.payment.plan_id)
        self.assertIsNone(payload['valid_until'])

    @patch('amuse.api.base.viewsets.subscription.subscription_canceled')
    def test_destroy(self, mocked_segment):
        response = self.client.delete(self.url)

        self.subscription.refresh_from_db()
        self.assertEqual(self.subscription.valid_until, self.payment.paid_until.date())
        self.assertEqual(self.subscription.status, Subscription.STATUS_ACTIVE)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertTrue(self.subscription.user.is_pro)
        mocked_segment.assert_called_once_with(self.subscription, '', '127.0.0.1')

    @patch('amuse.api.base.viewsets.subscription.subscription_canceled')
    def test_destroy_with_plan_invalidation(self, mocked_segment):
        new_plan = SubscriptionPlanFactory()
        plan_change = SubscriptionPlanChanges.objects.create(
            subscription=self.subscription,
            current_plan=self.subscription.plan,
            new_plan=new_plan,
        )
        response = self.client.delete(self.url)
        plan_change.refresh_from_db()
        self.subscription.refresh_from_db()
        self.assertEqual(self.subscription.valid_until, self.payment.paid_until.date())
        self.assertEqual(self.subscription.status, Subscription.STATUS_ACTIVE)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertTrue(self.subscription.user.is_pro)
        self.assertEqual(plan_change.valid, False)
        mocked_segment.assert_called_once_with(self.subscription, '', '127.0.0.1')

    @patch('amuse.api.base.viewsets.subscription.subscription_canceled')
    def test_destroy_twice_second_try_throws_404(self, mocked_segment):
        response = self.client.delete(self.url)

        self.subscription.refresh_from_db()
        self.assertEqual(self.subscription.valid_until, self.payment.paid_until.date())
        self.assertEqual(self.subscription.status, Subscription.STATUS_ACTIVE)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertTrue(self.subscription.user.is_pro)
        mocked_segment.assert_called_once_with(self.subscription, '', '127.0.0.1')
        mocked_segment.reset_mock()

        response = self.client.delete(self.url)

        self.subscription.refresh_from_db()
        self.assertEqual(self.subscription.valid_until, self.payment.paid_until.date())
        self.assertEqual(self.subscription.status, Subscription.STATUS_ACTIVE)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertTrue(self.subscription.user.is_pro)
        mocked_segment.assert_not_called()

    @patch('amuse.api.base.viewsets.subscription.subscription_canceled')
    def test_destroy_no_payments_sets_valid_until_to_paid_until(self, mocked_segment):
        self.subscription.paymenttransaction_set.all().delete()
        response = self.client.delete(self.url)

        self.subscription.refresh_from_db()
        self.assertEqual(self.subscription.valid_until, self.subscription.paid_until)
        self.assertEqual(self.subscription.status, Subscription.STATUS_ACTIVE)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertTrue(self.subscription.user.is_pro)
        mocked_segment.assert_called_once_with(self.subscription, '', '127.0.0.1')

    @patch('amuse.api.base.views.subscription.subscription.subscription_changed')
    def test_update(self, mocked_segment):
        new_plan = SubscriptionPlanFactory()
        url = reverse('update-current-subscription-plan')
        country = self.subscription.latest_payment().country

        response = self.client.put(url, {'plan': new_plan.pk})

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.subscription.refresh_from_db()
        self.assertEqual(self.subscription.status, Subscription.STATUS_ACTIVE)
        self.assertEqual(Subscription.objects.count(), 1)
        self.assertEqual(self.subscription.plan, new_plan)
        mocked_segment.assert_called_once_with(
            self.subscription, self.plan, new_plan, '', '127.0.0.1', country.code
        )

    def test_update_no_plan_selected_raises_error(self):
        url = reverse('update-current-subscription-plan')
        error_message = 'Subscription Plan does not exist'
        response = self.client.put(url, {})
        assert response.data['detail'] == error_message
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    @patch('amuse.api.base.views.subscription.subscription.logger')
    def test_update_no_existing_plan_raises_error(self, mock_logger):
        url = reverse('update-current-subscription-plan')
        error_message = 'Subscription Plan does not exist'
        response = self.client.put(url, {'plan': 'asd1234'})
        assert response.data['detail'] == error_message
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        mock_logger.warning.assert_called_once()

    @responses.activate
    @patch('amuse.api.base.views.subscription.subscription.subscription_new_started')
    def test_reactivate_subscription_unsets_valid_until_and_creates_auth_transaction(
        self, mocked_segment
    ):
        country = CountryFactory(is_adyen_enabled=True)
        new_plan = SubscriptionPlanFactory(trial_days=0)
        url = reverse('create-adyen-subscription')
        payment_details = mock_payment_details()
        self.user = self.subscription.user
        self._add_country_check_response(country.code)
        self._add_checkout_response('Authorised')
        self.subscription.valid_until = self.subscription.paid_until
        self.subscription.save()

        response = self.client.post(
            url,
            {
                'country': country.code,
                'plan': new_plan.pk,
                'payment_details': payment_details,
            },
            format='json',
        )
        self.subscription.refresh_from_db()

        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.json())
        self.assertTrue(response.data['is_success'], response.data)
        mocked_segment.assert_called_once_with(
            self.user.current_subscription(),
            PlatformType.WEB,
            '',
            '127.0.0.1',
            NONLOCALIZED_PAYMENTS_COUNTRY,
        )
        self.assertIsNone(self.subscription.valid_until)
        self.assertEqual(self.subscription.plan, new_plan)
        self.assertEqual(self.subscription.paymenttransaction_set.count(), 2)
        for payment_transaction in self.subscription.paymenttransaction_set.all():
            self.assertEqual(
                payment_transaction.paid_until.date(), self.subscription.paid_until
            )


class ActiveFreeSubscriptionTestCase(AmuseAPITestCase):
    @responses.activate
    def setUp(self):
        self.plan = SubscriptionPlanFactory(price=0)
        self.subscription = SubscriptionFactory(plan=self.plan)
        self.url = reverse('subscription-list')
        self.client.force_authenticate(self.subscription.user)
        self.client.credentials(HTTP_ACCEPT=API_V4_ACCEPT_VALUE)

    def test_list(self):
        payload = self.client.get(self.url).json()

        self.assertIsNone(payload['paid_until'])
        self.assertEqual(payload['plan']['id'], self.subscription.plan_id)
        self.assertEqual(
            payload['valid_from'], self.subscription.valid_from.isoformat()
        )
        self.assertIsNone(payload['valid_until'])

    def test_destroy(self):
        response = self.client.delete(self.url)

        self.subscription.refresh_from_db()
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertIsNone(self.subscription.valid_until)
        self.assertTrue(self.subscription.user.is_pro)

    def test_update(self):
        new_plan = SubscriptionPlanFactory()
        url = reverse('update-current-subscription-plan')
        response = self.client.put(url, {'plan': new_plan.pk})

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


class NoSubscriptionTestCase(AmuseAPITestCase):
    @responses.activate
    def setUp(self):
        add_zendesk_mock_post_response()
        self.user = UserFactory()
        self.url = reverse('subscription-list')
        self.client.credentials(HTTP_ACCEPT=API_V4_ACCEPT_VALUE)
        self.client.force_authenticate(self.user)

    def test_list_returns_404(self):
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_destroy(self):
        response = self.client.delete(self.url)

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_update(self):
        new_plan = SubscriptionPlanFactory()

        url = reverse('update-current-subscription-plan')

        response = self.client.put(url, {'plan': new_plan.pk})

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_update_payment_method_returns_404(self):
        url = reverse('update-current-payment-method')

        response = self.client.put(url, {}, format='json')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


class ActiveAppleSubscriptionTestCase(AmuseAPITestCase):
    @responses.activate
    def setUp(self):
        add_zendesk_mock_post_response()
        self.user = UserFactory()
        self.payment = PaymentTransactionFactory(
            subscription__plan__trial_days=0,
            subscription__provider=Subscription.PROVIDER_IOS,
            user=self.user,
        )
        self.subscription = self.payment.subscription
        self.url = reverse('subscription-list')
        self.client.force_authenticate(self.user)
        self.client.credentials(HTTP_ACCEPT=API_V4_ACCEPT_VALUE)

    def test_list(self):
        response = self.client.get(self.url)
        payload = response.json()

        self.assertEqual(response.status_code, status.HTTP_200_OK, payload)
        self.assertEqual(payload['plan']['id'], self.subscription.plan_id)
        self.assertEqual(payload['plan']['id'], self.subscription.plan_id)
        self.assertTrue(payload['valid_from'])
        self.assertTrue(payload['paid_until'])


class PlusToProPlanChangeNoAllowedTestCase(AmuseAPITestCase):
    @responses.activate
    def setUp(self):
        self.plan = SubscriptionPlanFactory(tier=SubscriptionPlan.TIER_PLUS)
        self.subscription = SubscriptionFactory(plan=self.plan)
        self.client.force_authenticate(self.subscription.user)
        self.payment = PaymentTransactionFactory(
            subscription=self.subscription,
            type=PaymentTransaction.TYPE_AUTHORISATION,
            user=self.subscription.user,
        )
        self.client.credentials(HTTP_ACCEPT=API_V4_ACCEPT_VALUE)

    def test_update_not_allowed(self):
        new_plan = SubscriptionPlanFactory(tier=SubscriptionPlan.TIER_PRO)
        url = reverse('update-current-subscription-plan')
        response = self.client.put(url, {'plan': new_plan.pk})
        error_message = 'Plan change from TIER_PLUS to TIER_PRO not implemented.'

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data['plan'], error_message)


class ProToPlusPlanChangeDowngradeCase(AmuseAPITestCase):
    @responses.activate
    def setUp(self):
        self.plan = SubscriptionPlanFactory(tier=SubscriptionPlan.TIER_PRO)
        self.subscription = SubscriptionFactory(plan=self.plan)
        self.client.force_authenticate(self.subscription.user)
        self.payment = PaymentTransactionFactory(
            subscription=self.subscription,
            type=PaymentTransaction.TYPE_AUTHORISATION,
            user=self.subscription.user,
        )
        self.client.credentials(HTTP_ACCEPT=API_V4_ACCEPT_VALUE)

    def test_update_not_allowed(self):
        new_plan = SubscriptionPlanFactory(tier=SubscriptionPlan.TIER_PLUS)
        url = reverse('update-current-subscription-plan')
        response = self.client.put(url, {'plan': new_plan.pk})

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        sub = Subscription.objects.get(id=self.subscription.id)
        # Assert plan is not changed#
        assert sub.plan.tier == SubscriptionPlan.TIER_PRO
        # Assert record created on SubscriptionPlanChanges
        pending = SubscriptionPlanChanges.objects.get(
            subscription=self.subscription, new_plan=new_plan
        )
        assert pending
        assert pending.valid == True
        assert pending.completed == False


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
    def test_non_adyen_delete_is_forbidden(self):
        url = reverse('subscription-list')
        for provider in self.non_adyen_providers:
            with self.subTest(msg=f'Delete "{provider[1]}" subscription'):
                subscription = SubscriptionFactory(
                    user=self.user, plan=self.plan, provider=provider[0]
                )

                response = self.client.delete(url)

                self.assertEqual(status.HTTP_400_BAD_REQUEST, response.status_code)
                self.assertEqual(self.expected_response, response.json())

    @responses.activate
    def test_non_adyen_reactivate_is_forbidden(
        self,
    ):
        url = reverse('create-adyen-subscription')

        country = self.country.code
        plan = self.plan.pk
        payment_details = mock_payment_details()

        headers = {'HTTP_USER_AGENT': 'amuse-android/3.4.41; WiFi'}
        for provider in self.non_adyen_providers:
            with self.subTest(msg=f'Reactivate "{provider[1]}" subscription'):
                subscription = SubscriptionFactory(
                    user=self.user, plan=self.plan, provider=provider[0]
                )

                response = self.client.post(
                    url,
                    {
                        'country': country,
                        'plan': plan,
                        'payment_details': payment_details,
                    },
                    format='json',
                    **headers,
                )

                self.assertEqual(status.HTTP_400_BAD_REQUEST, response.status_code)
                self.assertEqual(self.expected_response, response.json())

    @responses.activate
    def test_non_adyen_update_is_forbidden(self):
        new_plan = SubscriptionPlanFactory()
        url = reverse('update-current-subscription-plan')

        for provider in self.non_adyen_providers:
            with self.subTest(msg=f'Update (change plan) "{provider[1]}" subscription'):
                subscription = SubscriptionFactory(
                    user=self.user, plan=self.plan, provider=provider[0]
                )

                response = self.client.put(url, {'plan': new_plan.pk})

                self.assertEqual(status.HTTP_400_BAD_REQUEST, response.status_code)
                self.assertEqual(self.expected_response, response.json())
