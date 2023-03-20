import json
from datetime import timedelta
from decimal import Decimal
from unittest import skip
from unittest.mock import patch
from dateutil.relativedelta import relativedelta

import responses
from django.conf import settings
from django.urls import reverse
from django.utils import timezone
from rest_framework import status

from amuse.api.v5.serializers.subscription import (
    AppleSubscriptionSerializer as AppleSubscriptionV5Serializer,
)
from amuse.platform import PlatformType
from amuse.tests.helpers import add_zendesk_mock_post_response
from amuse.tests.test_api.base import AmuseAPITestCase, API_V5_ACCEPT_VALUE
from amuse.tests.test_vendor.test_adyen.base import AdyenBaseTestCase
from amuse.tests.test_vendor.test_adyen.helpers import mock_payment_details
from amuse.vendor.apple.subscriptions import (
    AppleReceiptValidationAPIClient as AppleClient,
)
from countries.tests.factories import CountryFactory, CurrencyFactory
from payments.models import PaymentTransaction
from payments.tests.factories import PaymentTransactionFactory
from subscriptions.models import Subscription, PriceCard, SubscriptionPlan
from subscriptions.tests.factories import (
    SubscriptionPlanFactory,
    SubscriptionFactory,
    PriceCardFactory,
    IntroductoryPriceCardFactory,
)
from subscriptions.vendor.apple.commons import parse_timestamp_ms
from users.models import User
from users.tests.factories import UserFactory


class CreateSubscriptionTestCase(AmuseAPITestCase, AdyenBaseTestCase):
    @responses.activate
    def setUp(self):
        add_zendesk_mock_post_response()
        self.country = CountryFactory(is_adyen_enabled=True)
        self.currency = CurrencyFactory()
        self.user = UserFactory()
        self.plan = SubscriptionPlanFactory(
            countries=[self.country], currency=self.currency
        )
        self.client.force_authenticate(self.user)
        self.client.credentials(HTTP_ACCEPT=API_V5_ACCEPT_VALUE)
        self.url = reverse('create-adyen-subscription')

    @responses.activate
    @patch('amuse.api.base.views.subscription.subscription.subscription_new_started')
    def test_create_subscription_is_successful_web(self, mocked_segment):
        self._add_country_check_response(self.country.code)
        self._add_checkout_response('Authorised')
        country = self.country.code
        plan = self.plan.pk
        payment_details = mock_payment_details()

        web_user_agent = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:80.0) Gecko/20100101 Firefox/80.0'
        headers = {'HTTP_USER_AGENT': web_user_agent}
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
            PlatformType.WEB,
            web_user_agent,
            '127.0.0.1',
            country,
        )
        self.assertEqual(
            self.user.current_subscription().latest_payment().category,
            PaymentTransaction.CATEGORY_INITIAL,
        )
        self.assertEqual(
            self.user.current_subscription().latest_payment().platform,
            PaymentTransaction.PLATFORM_WEB,
        )

    @responses.activate
    @patch('amuse.api.base.views.subscription.subscription.subscription_new_started')
    def test_create_introductory_subscription_is_successful(self, _):
        introductory_card = IntroductoryPriceCardFactory(
            plan=self.plan,
            price=Decimal('1.23'),
            period=2,
            currency=self.currency,
            countries=[self.country],
        )

        self._add_country_check_response(self.country.code)
        self._add_checkout_response('Authorised')

        response = self.client.post(
            self.url,
            {
                'country': self.country.code,
                'plan': self.plan.pk,
                'payment_details': mock_payment_details(),
                'is_introductory_price': True,
            },
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(response.data['is_success'], response.data)

        subscription = self.user.current_subscription()
        payment = subscription.latest_payment()
        self.assertEqual(PaymentTransaction.TYPE_INTRODUCTORY_PAYMENT, payment.type)
        expected_paid_until = timezone.now() + relativedelta(
            months=introductory_card.period
        )
        self.assertEqual(expected_paid_until.date(), payment.paid_until.date())

    @responses.activate
    @patch('amuse.api.base.views.subscription.subscription.subscription_new_started')
    def test_create_introductory_subscription_is_not_successful(self, _):
        self._add_country_check_response(self.country.code)
        self._add_checkout_response('Authorised')

        response = self.client.post(
            self.url,
            {
                'country': self.country.code,
                'plan': self.plan.pk,
                'payment_details': mock_payment_details(),
                'is_introductory_price': True,
            },
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(
            response.data['is_introductory_price'],
            'Introductory price is not available',
        )

    @responses.activate
    @patch('amuse.api.base.views.subscription.subscription.subscription_new_started')
    def test_block_double_subscription_create(self, mocked_segment):
        self._add_country_check_response(self.country.code)
        self._add_checkout_response('Authorised')
        country = self.country.code
        plan = self.plan.pk
        payment_details = mock_payment_details()
        error_message = 'You already have an active subscription.'

        SubscriptionFactory(user=self.user)

        web_user_agent = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:80.0) Gecko/20100101 Firefox/80.0'
        headers = {'HTTP_USER_AGENT': web_user_agent}
        response = self.client.post(
            self.url,
            {'country': country, 'plan': plan, 'payment_details': payment_details},
            format='json',
            **headers,
        )
        self.assertEqual(response.data['detail'], error_message)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    @skip("Skipping until this validation is enabled")
    @responses.activate
    @patch('amuse.api.base.views.subscription.subscription_new_started')
    def test_billing_address_is_required_for_selected_countries(self, mocked_segment):
        country = CountryFactory(code='US', is_adyen_enabled=True)
        price_card = PriceCardFactory(plan=self.plan, countries=[country])
        self._add_country_check_response(country.code)
        self._add_checkout_response('Authorised')
        plan = self.plan.pk
        payment_details = mock_payment_details()
        del payment_details['billingAddress']

        response = self.client.post(
            self.url,
            {'country': country.code, 'plan': plan, 'payment_details': payment_details},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        self._add_country_check_response(country.code)
        payment_details = mock_payment_details()

        response = self.client.post(
            self.url,
            {'country': country.code, 'plan': plan, 'payment_details': payment_details},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    @responses.activate
    @patch('amuse.api.base.views.subscription.subscription.subscription_new_started')
    def test_create_subscription_is_successful(self, mocked_segment):
        self._add_country_check_response(self.country.code)
        self._add_checkout_response('Authorised')
        self.plan.trial_days = 0
        self.plan.save()

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

        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.assertTrue(response.data['is_success'], response.data)
        mocked_segment.assert_called_once_with(
            self.user.current_subscription(),
            PlatformType.ANDROID,
            'amuse-android/3.4.41; WiFi',
            '127.0.0.1',
            country,
        )
        self.assertEqual(
            self.user.current_subscription().latest_payment().category,
            PaymentTransaction.CATEGORY_INITIAL,
        )
        self.assertEqual(
            self.user.current_subscription().latest_payment().amount,
            self.plan.get_price_card(country).price,
        )
        self.assertEqual(
            self.user.current_subscription().latest_payment().country, self.country
        )
        self.assertEqual(
            self.user.current_subscription().latest_payment().platform,
            PaymentTransaction.PLATFORM_ANDROID,
        )

    @responses.activate
    @patch('amuse.api.base.views.subscription.subscription.subscription_new_started')
    def test_free_sub_active_returns_active_subscription_error(self, mocked_segment):
        self._add_country_check_response(self.country.code)
        self._add_checkout_response('Authorised')
        card = self.plan.pricecard_set.first()
        card.price = 0
        card.save()
        subscription = SubscriptionFactory(
            user=self.user,
            plan=self.plan,
            valid_until=timezone.now() + timezone.timedelta(days=30),
        )

        country = self.country.code
        plan = self.plan.pk
        payment_details = mock_payment_details()

        response = self.client.post(
            self.url,
            {'country': country, 'plan': plan, 'payment_details': payment_details},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(
            str(response.data['detail']), 'You already have an active subscription.'
        )

    @responses.activate
    @patch('amuse.api.base.views.subscription.subscription.subscription_new_started')
    def test_create_sub_uses_usd_price_for_country_mismatch(self, mocked_segment):
        # delete price card for self.country so the default USD price card is used
        self.plan.pricecard_set.all().delete()

        # create the default price card for US
        country = CountryFactory(code='US', is_adyen_enabled=True)
        card = PriceCardFactory(plan=self.plan, countries=[country])
        self._add_country_check_response(self.country.code)
        self._add_checkout_response('Authorised')
        self.plan.trial_days = 0
        self.plan.save()
        payment_details = mock_payment_details()

        payload = {
            'country': self.country.code,
            'plan': self.plan.pk,
            'payment_details': payment_details,
        }

        response = self.client.post(self.url, payload, format='json')

        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.assertTrue(response.data['is_success'], response.data)
        mocked_segment.assert_called_once_with(
            self.user.current_subscription(),
            PlatformType.WEB,
            '',
            '127.0.0.1',
            self.country.code,
        )
        self.assertEqual(
            self.user.current_subscription().latest_payment().category,
            PaymentTransaction.CATEGORY_INITIAL,
        )
        self.assertEqual(
            self.user.current_subscription().latest_payment().amount, card.price
        )
        self.assertEqual(
            self.user.current_subscription().latest_payment().currency, card.currency
        )
        self.assertEqual(
            self.user.current_subscription().latest_payment().country, self.country
        )


class CurrentSubscriptionTestCase(AmuseAPITestCase):
    @responses.activate
    def setUp(self):
        add_zendesk_mock_post_response()
        self.country = CountryFactory(code='JJ')
        self.user = UserFactory()

        self.plan = SubscriptionPlanFactory(countries=[self.country], create_card=False)
        self.price_card = PriceCardFactory(countries=[self.country], plan=self.plan)
        self.subscription = SubscriptionFactory(user=self.user, plan=self.plan)
        self.payment = PaymentTransactionFactory(
            subscription=self.subscription,
            user=self.user,
            country=self.country,
            plan=self.plan,
            currency=self.price_card.currency,
            amount=self.price_card.price,
        )

        self.client.force_authenticate(self.user)
        self.client.credentials(HTTP_ACCEPT=API_V5_ACCEPT_VALUE)
        self.url = reverse('subscription-list')

    @patch.object(User, 'current_entitled_subscription', return_value=None)
    def test_current_entitled_subscription_is_executed(self, mock_entitled):
        response = self.client.get(path=self.url, format='json')
        mock_entitled.assert_called_once()

    def test_current_subscription_is_returned_for_right_country(self):
        response = self.client.get(path=self.url, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        data = response.data
        self.assertEqual(
            self.price_card.currency.code, data['current_plan']['currency']
        )
        self.assertEqual(self.country.code, data['current_plan']['country'])

        self.assertEqual(self.price_card.currency.code, data['plan']['currency'])
        self.assertEqual(self.country.code, data['plan']['country'])

    def test_correct_currency_and_price_is_returned_for_non_localised_subs(self):
        # If a User has a legacy non-localised Subscription, we keep that currency
        # instead of moving the pricing to localised model
        legacy_price_card = PriceCardFactory(plan=self.plan)
        self.payment.currency = legacy_price_card.currency
        self.payment.save()

        # the User now has his Country set as usual, but the currency is legacy
        self.assertEqual(self.payment.country, self.country)
        self.assertEqual(self.payment.currency, legacy_price_card.currency)

        response = self.client.get(path=self.url, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        data = response.data
        self.assertEqual(
            legacy_price_card.currency.code, data['current_plan']['currency']
        )
        self.assertEqual(self.country.code, data['current_plan']['country'])
        self.assertEqual(str(legacy_price_card.price), data['current_plan']['price'])

        self.assertEqual(legacy_price_card.currency.code, data['plan']['currency'])
        self.assertEqual(self.country.code, data['plan']['country'])
        self.assertEqual(str(legacy_price_card.price), data['plan']['price'])

    def test_price_is_pulled_from_latest_transaction_if_price_card_missing(self):
        period_price = self.price_card.period_price
        PriceCard.objects.all().delete()
        response = self.client.get(path=self.url, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        data = response.data
        self.assertEqual(self.payment.currency.code, data['current_plan']['currency'])
        self.assertEqual(str(self.payment.amount), data['current_plan']['price'])
        self.assertEqual(str(period_price), data['current_plan']['period_price'])
        self.assertEqual(self.country.code, data['current_plan']['country'])

        self.assertEqual(self.payment.currency.code, data['plan']['currency'])
        self.assertEqual(str(self.payment.amount), data['plan']['price'])
        self.assertEqual(str(period_price), data['plan']['period_price'])
        self.assertEqual(self.country.code, data['plan']['country'])

    def test_bad_data_raises_api_exception(self):
        PriceCard.objects.all().delete()
        PaymentTransaction.objects.all().delete()
        response = self.client.get(path=self.url, format='json')
        self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
        self.assertEqual(
            str(response.data['detail']),
            'There is an error with your Subscription. Please contact Amuse support.',
        )

    @patch('amuse.api.base.viewsets.subscription.subscription_canceled')
    def test_destroy_with_wrong_provider(self, _):
        self.subscription.provider = Subscription.PROVIDER_GOOGLE
        self.subscription.save()

        response = self.client.delete(self.url)

        self.assertEqual(status.HTTP_400_BAD_REQUEST, response.status_code)


class CurrentSubscriptionVIPusersTestCase(AmuseAPITestCase):
    @responses.activate
    def setUp(self):
        add_zendesk_mock_post_response()
        self.country = CountryFactory(code='JJ')
        self.default_country = CountryFactory(code='US')
        self.currency = CurrencyFactory(code='USD')

        self.user = UserFactory()
        self.plan = SubscriptionPlanFactory(
            countries=[self.country, self.default_country],
            create_card=False,
            is_public=False,
            name='VIP Plan',
        )

        self.price_card = PriceCardFactory(
            countries=[self.country, self.default_country],
            plan=self.plan,
            currency=self.currency,
        )
        self.subscription = SubscriptionFactory(user=self.user, plan=self.plan)

        self.client.force_authenticate(self.user)
        self.client.credentials(HTTP_ACCEPT=API_V5_ACCEPT_VALUE)
        self.url = reverse('subscription-list')

    def test_current_subscription_is_returned_for_vip_users(self):
        response = self.client.get(path=self.url, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        data = response.data
        self.assertEqual(
            self.price_card.currency.code, data['current_plan']['currency']
        )
        self.assertEqual(self.default_country.code, data['current_plan']['country'])

        self.assertEqual(self.currency.code, data['plan']['currency'])
        self.assertEqual(self.default_country.code, data['plan']['country'])


class CreateAppleSubscriptionTestCase(AmuseAPITestCase, AdyenBaseTestCase):
    @responses.activate
    def setUp(self):
        add_zendesk_mock_post_response()
        self.country = CountryFactory(code='FK')
        self.user = UserFactory()
        self.plan = SubscriptionPlanFactory(
            apple_product_id='test', countries=[self.country]
        )
        self.client.force_authenticate(self.user)
        self.client.credentials(HTTP_ACCEPT=API_V5_ACCEPT_VALUE)
        self.url = reverse('create-apple-subscription')

    @responses.activate
    @patch.object(AppleClient, 'validate_receipt')
    @patch.object(AppleClient, 'get_original_transaction_id')
    @patch.object(AppleClient, 'get_transaction_id')
    @patch.object(AppleClient, 'get_product_id')
    @patch.object(AppleClient, 'get_expires_date')
    @patch.object(AppleClient, 'get_purchase_date')
    @patch.object(AppleClient, 'get_is_in_intro_offer')
    def test_create_subscription_is_successful(
        self,
        mock_get_is_in_intro_offer,
        mock_purchase_data,
        mock_get_expires_date,
        mock_get_product_id,
        mock_get_transaction_id,
        mock_get_original_transaction_id,
        mock_validate_receipt,
    ):
        mock_validate_receipt.return_value = None
        mock_get_original_transaction_id.return_value = 'fake-original-transaction-id'
        mock_get_transaction_id.return_value = 'fake-transaction-id'
        mock_get_product_id.return_value = 'test'
        mock_purchase_data.return_value = timezone.now()
        mock_get_expires_date.return_value = timezone.now() + timedelta(days=30)
        mock_get_is_in_intro_offer.return_value = False

        response = self.client.post(
            self.url,
            {'country': self.country.code, 'receipt_data': "fake-receipt-data"},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(
            self.user.current_subscription().latest_payment().platform,
            PaymentTransaction.PLATFORM_IOS,
        )

    @responses.activate
    @patch.object(AppleClient, 'validate_receipt')
    @patch.object(AppleClient, 'get_original_transaction_id')
    @patch.object(AppleClient, 'get_transaction_id')
    @patch.object(AppleClient, 'get_product_id')
    @patch.object(AppleClient, 'get_expires_date')
    @patch.object(AppleClient, 'get_purchase_date')
    @patch.object(AppleClient, 'get_is_in_intro_offer')
    def test_create_subscription_with_intro_price_is_successful(
        self,
        mock_get_is_in_intro_offer,
        mock_purchase_data,
        mock_get_expires_date,
        mock_get_product_id,
        mock_get_transaction_id,
        mock_get_original_transaction_id,
        mock_validate_receipt,
    ):
        mock_validate_receipt.return_value = None
        mock_get_original_transaction_id.return_value = 'fake-original-transaction-id'
        mock_get_transaction_id.return_value = 'fake-transaction-id'
        mock_get_product_id.return_value = 'test'
        mock_purchase_data.return_value = timezone.now()
        mock_get_expires_date.return_value = timezone.now() + timedelta(days=30)
        mock_get_is_in_intro_offer.return_value = True

        intoductory_card = IntroductoryPriceCardFactory(
            plan=self.plan, countries=[self.country]
        )
        response = self.client.post(
            self.url,
            {'country': self.country.code, 'receipt_data': "fake-receipt-data"},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(
            self.user.current_subscription().latest_payment().platform,
            PaymentTransaction.PLATFORM_IOS,
        )
        self.assertEqual(
            self.user.current_subscription().latest_payment().type,
            PaymentTransaction.TYPE_INTRODUCTORY_PAYMENT,
        )
        self.assertEqual(
            intoductory_card.price,
            self.user.current_subscription().latest_payment().amount,
        )

    @responses.activate
    @patch.object(AppleClient, 'validate_receipt')
    @patch.object(AppleClient, 'get_original_transaction_id')
    @patch.object(AppleClient, 'get_transaction_id')
    @patch.object(AppleClient, 'get_product_id')
    @patch.object(AppleClient, 'get_expires_date')
    def test_apple_block_double_subscription_create(
        self,
        mock_get_expires_date,
        mock_get_product_id,
        mock_get_transaction_id,
        mock_get_original_transaction_id,
        mock_validate_receipt,
    ):
        mock_validate_receipt.return_value = None
        mock_get_original_transaction_id.return_value = 'fake-original-transaction-id'
        mock_get_transaction_id.return_value = 'fake-transaction-id'
        mock_get_product_id.return_value = self.plan.apple_product_id
        mock_get_expires_date.return_value = timezone.now() + timedelta(days=30)

        SubscriptionFactory(user=self.user)
        error_message = 'You already have an active subscription.'

        response = self.client.post(
            self.url,
            {'country': self.country.code, 'receipt_data': "fake-receipt-data"},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(response.data['detail'], error_message)


class AppleSubscriptionGetCountryTestCase(AmuseAPITestCase, AdyenBaseTestCase):
    @responses.activate
    def setUp(self):
        add_zendesk_mock_post_response()
        self.country_fk = CountryFactory(code='FK')
        self.country_us = CountryFactory(code='US')
        self.country_se = CountryFactory(code='SE')
        self.user1 = UserFactory(country='US')
        self.user2 = UserFactory()
        self.plan = SubscriptionPlanFactory(countries=[self.country_fk])
        self.client.force_authenticate(self.user1)
        self.client.credentials(HTTP_ACCEPT=API_V5_ACCEPT_VALUE)
        self.url = reverse('create-apple-subscription')

    def test_get_country_success(self):
        serializer = AppleSubscriptionV5Serializer()
        serializer._validated_data = {"country": self.country_fk.code}

        country = serializer._get_country(self.user1)

        self.assertEqual(self.country_fk, country)

    def test_get_country_fallback_from_user(self):
        serializer = AppleSubscriptionV5Serializer()
        serializer._validated_data = {"country": "zz"}

        country = serializer._get_country(self.user1)

        self.assertEqual(self.user1.country, country.code)

    def test_get_country_fallback_default_country(self):
        serializer = AppleSubscriptionV5Serializer()
        serializer._validated_data = {"country": "zz"}

        DEFAULT_APPLE_COUNTRY = 'SE'
        country = serializer._get_country(self.user2)

        self.assertEqual(DEFAULT_APPLE_COUNTRY, country.code)


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


class CreateAppleSubscriptionExtendedTestCase(AmuseAPITestCase):
    @responses.activate
    def setUp(self):
        add_zendesk_mock_post_response()
        self.country = CountryFactory(code='FK')
        self.user = UserFactory()
        self.plan = SubscriptionPlanFactory(
            apple_product_id='amuse_boost_yearly_renewal_notrial',
            tier=SubscriptionPlan.TIER_PLUS,
        )
        self.client.force_authenticate(self.user)
        self.client.credentials(HTTP_ACCEPT=API_V5_ACCEPT_VALUE)
        self.url = reverse('create-apple-subscription')

    @responses.activate
    def test_create_subscription_is_successful(self):
        rd = {
            "environment": "Production",
            "receipt": {
                "receipt_type": "Production",
                "adam_id": 1160922922,
                "app_item_id": 1160922922,
                "bundle_id": "io.amuse.ios",
                "application_version": "2913",
                "download_id": 92071437973739,
                "version_external_identifier": 840940425,
                "receipt_creation_date": "2021-03-29 08:09:39 Etc/GMT",
                "receipt_creation_date_ms": "1617005379000",
                "receipt_creation_date_pst": "2021-03-29 01:09:39 America/Los_Angeles",
                "request_date": "2021-03-29 09:41:08 Etc/GMT",
                "request_date_ms": "1617010868501",
                "request_date_pst": "2021-03-29 02:41:08 America/Los_Angeles",
                "original_purchase_date": "2021-02-02 16:17:10 Etc/GMT",
                "original_purchase_date_ms": "1612282630000",
                "original_purchase_date_pst": "2021-02-02 08:17:10 America/Los_Angeles",
                "original_application_version": "2646",
            },
            "latest_receipt_info": [
                {
                    "quantity": "1",
                    "product_id": "amuse_boost_yearly_renewal_notrial",
                    "transaction_id": "520000761510694",
                    "original_transaction_id": "520000723529084",
                    "purchase_date": "2021-03-29 08:09:38 Etc/GMT",
                    "purchase_date_ms": "1616005378000",
                    "purchase_date_pst": "2021-03-29 01:09:38 America/Los_Angeles",
                    "original_purchase_date": "2021-02-02 17:01:28 Etc/GMT",
                    "original_purchase_date_ms": "1612285288000",
                    "original_purchase_date_pst": "2021-02-02 09:01:28 America/Los_Angeles",
                    "expires_date": "2022-03-29 08:09:38 Etc/GMT",
                    "expires_date_ms": "1648541378000",
                    "expires_date_pst": "2022-03-29 01:09:38 America/Los_Angeles",
                    "web_order_line_item_id": "520000289995015",
                    "is_trial_period": "false",
                    "is_in_intro_offer_period": "false",
                    "in_app_ownership_type": "PURCHASED",
                    "subscription_group_identifier": "20581044",
                },
                {
                    "quantity": "1",
                    "product_id": "amuse_pro_monthly_renewal",
                    "transaction_id": "520000723529084",
                    "original_transaction_id": "520000723529084",
                    "purchase_date": "2021-02-02 17:01:26 Etc/GMT",
                    "purchase_date_ms": "1612285286000",
                    "purchase_date_pst": "2021-02-02 09:01:26 America/Los_Angeles",
                    "original_purchase_date": "2021-02-02 17:01:28 Etc/GMT",
                    "original_purchase_date_ms": "1612285288000",
                    "original_purchase_date_pst": "2021-02-02 09:01:28 America/Los_Angeles",
                    "expires_date": "2021-03-02 17:01:26 Etc/GMT",
                    "expires_date_ms": "1614704486000",
                    "expires_date_pst": "2021-03-02 09:01:26 America/Los_Angeles",
                    "web_order_line_item_id": "520000289995014",
                    "is_trial_period": "false",
                    "is_in_intro_offer_period": "false",
                    "in_app_ownership_type": "PURCHASED",
                    "subscription_group_identifier": "20581044",
                },
            ],
            "pending_renewal_info": [
                {
                    "auto_renew_product_id": "amuse_boost_yearly_renewal_notrial",
                    "product_id": "amuse_boost_yearly_renewal_notrial",
                    "original_transaction_id": "520000723529084",
                    "auto_renew_status": "1",
                }
            ],
            "status": 0,
        }

        responses.add(
            responses.POST, settings.APPLE_VALIDATION_URL, json.dumps(rd), status=200
        )

        last_tx_info = rd['latest_receipt_info'][0]
        paid_until = parse_timestamp_ms(last_tx_info['expires_date_ms'])
        purchase_date = parse_timestamp_ms(last_tx_info['purchase_date_ms'])

        response = self.client.post(
            self.url,
            {'country': self.country.code, 'receipt_data': "fake-receipt-data"},
            format='json',
        )
        sub = Subscription.objects.get(user=self.user)
        plan = sub.plan
        tx = sub.latest_payment()

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(sub.status, Subscription.STATUS_ACTIVE)
        self.assertEqual(plan.tier, SubscriptionPlan.TIER_PLUS)
        self.assertEqual(sub.valid_from, purchase_date.date())
        self.assertEqual(tx.status, PaymentTransaction.STATUS_APPROVED)
        self.assertEqual(tx.paid_until, paid_until)
        self.assertEqual(tx.external_transaction_id, '520000761510694')
        self.assertEqual(tx.created, purchase_date)
        self.assertEqual(
            self.user.current_subscription().latest_payment().platform,
            PaymentTransaction.PLATFORM_IOS,
        )
