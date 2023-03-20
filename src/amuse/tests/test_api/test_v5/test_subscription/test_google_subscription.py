import base64
from datetime import datetime, timedelta
from decimal import Decimal
from unittest.mock import patch

import responses
from django.urls import reverse
from django.utils import timezone
from django.utils.timezone import make_aware
from rest_framework import status

from amuse.platform import PlatformType
from amuse.tests.helpers import add_zendesk_mock_post_response
from amuse.tests.test_api.base import (
    AmuseAPITestCase,
    API_V5_ACCEPT_VALUE,
    API_V4_ACCEPT_VALUE,
)
from countries.tests.factories import CountryFactory, CurrencyFactory
from payments.models import PaymentMethod, PaymentTransaction
from payments.tests.factories import PaymentMethodFactory
from subscriptions.models import Subscription
from subscriptions.tests.factories import SubscriptionFactory, SubscriptionPlanFactory
from subscriptions.vendor.google import GooglePlayAPI, PurchaseSubscription
from users.tests.factories import UserFactory


class CreateGoogleSubscriptionFailNonFreeUserTestCase(AmuseAPITestCase):
    @responses.activate
    def setUp(self):
        add_zendesk_mock_post_response()
        self.user = UserFactory()
        self.plan = SubscriptionPlanFactory(google_product_id='sku_123')
        self.subscription = SubscriptionFactory(
            user=self.user, plan=self.plan, status=Subscription.STATUS_ACTIVE
        )

        self.client.force_authenticate(self.user)
        self.client.credentials(HTTP_ACCEPT=API_V5_ACCEPT_VALUE)
        self.url = reverse('create-google-subscription')

    @responses.activate
    @patch.object(GooglePlayAPI, 'verify_purchase_token', return_value={})
    def test_forbidden_for_non_free_user(self, _):
        payload = {'google_subscription_id': 'sku_1234', 'purchase_token': 'pt_123'}
        response = self.client.post(self.url, payload, format='json')

        self.assertEqual(status.HTTP_403_FORBIDDEN, response.status_code)


class CreateGoogleSubscriptionFailTestCase(AmuseAPITestCase):
    @responses.activate
    def setUp(self):
        add_zendesk_mock_post_response()
        self.user = UserFactory()
        self.client.force_authenticate(self.user)
        self.client.credentials(HTTP_ACCEPT=API_V5_ACCEPT_VALUE)
        self.plan = SubscriptionPlanFactory(
            google_product_id='sku_123', google_product_id_trial='sku_123_NOTRIAL'
        )
        self.url = reverse('create-google-subscription')

    @responses.activate
    @patch.object(GooglePlayAPI, 'verify_purchase_token', return_value={})
    def test_bad_request_for_invalid_google_subscription_id(self, _):
        payload = {'google_subscription_id': 'sku_1234', 'purchase_token': 'pt_123'}
        response = self.client.post(self.url, payload, format='json')

        self.assertEqual(status.HTTP_400_BAD_REQUEST, response.status_code)
        self.assertIn('google_subscription_id', response.data)
        self.assertNotIn('purchase_token', response.data)

    @responses.activate
    @patch.object(GooglePlayAPI, 'verify_purchase_token', return_value={})
    def test_bad_request_for_free_trial_user_with_google_subscription_id(self, _):
        subscription = SubscriptionFactory(
            user=self.user,
            plan=self.plan,
            status=Subscription.STATUS_EXPIRED,
            free_trial_from=timezone.now() - timedelta(days=5),
            free_trial_until=timezone.now() + timedelta(days=5),
        )

        payload = {'google_subscription_id': 'sku_123', 'purchase_token': 'pt_123'}
        response = self.client.post(self.url, payload, format='json')

        self.assertEqual(status.HTTP_400_BAD_REQUEST, response.status_code)
        self.assertIn('google_subscription_id', response.data)
        self.assertNotIn('purchase_token', response.data)

    @responses.activate
    @patch.object(GooglePlayAPI, 'verify_purchase_token', return_value=None)
    def test_bad_request_for_invalid_purchase_token(self, _):
        payload = {'google_subscription_id': 'sku_123', 'purchase_token': 'pt_123'}
        response = self.client.post(self.url, payload, format='json')

        self.assertEqual(status.HTTP_400_BAD_REQUEST, response.status_code)
        self.assertNotIn('google_subscription_id', response.data)
        self.assertIn('purchase_token', response.data)

    @responses.activate
    @patch.object(GooglePlayAPI, 'verify_purchase_token', return_value={})
    def test_already_used_purchase_token(self, _):
        PaymentMethodFactory(external_recurring_id='pt_123')
        payload = {'google_subscription_id': 'sku_123', 'purchase_token': 'pt_123'}
        response = self.client.post(self.url, payload, format='json')

        self.assertEqual(status.HTTP_400_BAD_REQUEST, response.status_code)
        self.assertEqual(
            str(response.data['purchase_token']), 'Already used purchase_token.'
        )

    @responses.activate
    def test_bad_request_for_invalid_api_version(self):
        self.client.credentials(HTTP_ACCEPT=API_V4_ACCEPT_VALUE)

        response = self.client.post(self.url, {}, format='json')

        self.assertEqual(status.HTTP_400_BAD_REQUEST, response.status_code)
        self.assertIn('detail', response.data)
        self.assertEqual(response.json(), {'detail': 'API version is not supported.'})


class CreateGoogleSubscriptionSuccessTestCase(AmuseAPITestCase):
    @responses.activate
    def setUp(self):
        add_zendesk_mock_post_response()
        self.country = CountryFactory(code='FK', vat_percentage=0.1)
        self.currency = CurrencyFactory(code='FKD')
        self.user = UserFactory()
        self.plan = SubscriptionPlanFactory(
            countries=[self.country],
            google_product_id='sku_123',
            google_product_id_trial='sku_123_notrial',
        )
        self.client.force_authenticate(self.user)
        self.client.credentials(HTTP_ACCEPT=API_V5_ACCEPT_VALUE)
        self.url = reverse('create-google-subscription')

    @responses.activate
    @patch(
        'amuse.api.base.views.subscription.google_subscription.subscription_new_started'
    )
    @patch.object(GooglePlayAPI, 'verify_purchase_token')
    def test_create_subscription(self, mock_verify, mocked_segment_new):
        purchase = {
            'expiryTimeMillis': '1610645074',
            'priceAmountMicros': '1990000',
            'countryCode': 'FK',
            'priceCurrencyCode': 'FKD',
            'orderId': 'GOOGLE-TEST-SUB-123',
            'paymentState': 1,
            'autoRenewing': True,
        }
        mock_verify.return_value = purchase
        payload = {
            'google_subscription_id': 'sku_123_notrial',
            'purchase_token': 'pt_123',
        }

        android_user_agent = 'amuse-Android/3.12.1; Cellular'
        headers = {'HTTP_USER_AGENT': android_user_agent}
        response = self.client.post(self.url, payload, format='json', **headers)

        # test
        subscriptions = list(Subscription.objects.filter(user=self.user))
        transactions = list(PaymentTransaction.objects.filter(user=self.user))
        payment_methods = list(PaymentMethod.objects.filter(user=self.user))

        self.assertEqual(status.HTTP_201_CREATED, response.status_code)
        self.assertEqual(1, len(subscriptions), 'Subscription is not created')
        self.assertEqual(1, len(payment_methods), 'PaymentMethod is not created')
        self.assertEqual(1, len(transactions), 'Transaction is not created')

        # test payment method
        self.assertEqual('pt_123', payment_methods[0].external_recurring_id)
        self.assertEqual('GOOGL', payment_methods[0].method)

        # test subscription
        self.assertEqual(Subscription.STATUS_ACTIVE, subscriptions[0].status)
        self.assertEqual(Subscription.PROVIDER_GOOGLE, subscriptions[0].provider)
        self.assertEqual(payment_methods[0], subscriptions[0].payment_method)
        self.assertIsNone(subscriptions[0].valid_until)
        self.assertIsNone(subscriptions[0].grace_period_until)

        # test transaction
        self.assertEqual(Decimal('1.99'), transactions[0].amount)
        self.assertEqual(PaymentTransaction.CATEGORY_INITIAL, transactions[0].category)
        self.assertEqual('FK', transactions[0].country.code)
        self.assertEqual(payload, transactions[0].customer_payment_payload)
        self.assertEqual(purchase, transactions[0].external_payment_response)
        self.assertEqual(purchase['orderId'], transactions[0].external_transaction_id)
        self.assertEqual(payment_methods[0], transactions[0].payment_method)
        self.assertEqual(self.plan, transactions[0].plan)
        self.assertEqual(PaymentTransaction.STATUS_APPROVED, transactions[0].status)
        self.assertEqual(subscriptions[0], transactions[0].subscription)
        self.assertEqual(PaymentTransaction.TYPE_PAYMENT, transactions[0].type)
        self.assertEqual(self.user, transactions[0].user)
        self.assertEqual(0, transactions[0].vat_amount)
        self.assertEqual(0, transactions[0].vat_percentage)
        self.assertEqual(self.currency, transactions[0].currency)
        self.assertEqual(PaymentTransaction.PLATFORM_ANDROID, transactions[0].platform)

        # test analytics
        mocked_segment_new.assert_called_once_with(
            self.user.current_subscription(),
            PlatformType.ANDROID,
            android_user_agent,
            '127.0.0.1',
            self.country.code,
        )

    @responses.activate
    @patch(
        'amuse.api.base.views.subscription.google_subscription.subscription_trial_started'
    )
    @patch.object(GooglePlayAPI, 'verify_purchase_token')
    def test_create_free_trial_subscription(self, mock_verify, mocked_segment_new):
        expiry_timestamp = 1610645074
        start_timestamp = 1615647910

        purchase = {
            'expiryTimeMillis': str(expiry_timestamp * 1000),
            'startTimeMillis': str(start_timestamp * 1000),
            'priceAmountMicros': '1990000',
            'countryCode': 'FK',
            'priceCurrencyCode': 'FKD',
            'orderId': 'GOOGLE-TEST-SUB-123',
            'paymentState': 2,
            'autoRenewing': True,
        }
        mock_verify.return_value = purchase
        payload = {'google_subscription_id': 'sku_123', 'purchase_token': 'pt_123'}

        android_user_agent = 'amuse-Android/3.12.1; Cellular'
        headers = {'HTTP_USER_AGENT': android_user_agent}
        response = self.client.post(self.url, payload, format='json', **headers)

        # test
        subscriptions = list(Subscription.objects.filter(user=self.user))
        transactions = list(PaymentTransaction.objects.filter(user=self.user))
        payment_methods = list(PaymentMethod.objects.filter(user=self.user))

        self.assertEqual(status.HTTP_201_CREATED, response.status_code)
        self.assertEqual(1, len(subscriptions), 'Subscription is not created')
        self.assertEqual(1, len(payment_methods), 'PaymentMethod is not created')
        self.assertEqual(1, len(transactions), 'Transaction is not created')

        # test payment method
        self.assertEqual('pt_123', payment_methods[0].external_recurring_id)
        self.assertEqual('GOOGL', payment_methods[0].method)

        # test subscription
        self.assertEqual(Subscription.STATUS_ACTIVE, subscriptions[0].status)
        self.assertEqual(Subscription.PROVIDER_GOOGLE, subscriptions[0].provider)
        self.assertEqual(payment_methods[0], subscriptions[0].payment_method)
        self.assertIsNone(subscriptions[0].valid_until)
        self.assertIsNone(subscriptions[0].grace_period_until)

        self.assertIsNotNone(subscriptions[0].free_trial_from)
        self.assertIsNotNone(subscriptions[0].free_trial_until)

        expected_free_trial_from = make_aware(
            datetime.utcfromtimestamp(start_timestamp)
        )
        expected_free_trial_until = make_aware(
            datetime.utcfromtimestamp(expiry_timestamp)
        )

        self.assertEqual(expected_free_trial_from, subscriptions[0].free_trial_from)
        self.assertEqual(expected_free_trial_until, subscriptions[0].free_trial_until)

        # test transaction
        self.assertEqual(Decimal('0.0'), transactions[0].amount)
        self.assertEqual(PaymentTransaction.CATEGORY_INITIAL, transactions[0].category)
        self.assertEqual('FK', transactions[0].country.code)
        self.assertEqual(payload, transactions[0].customer_payment_payload)
        self.assertEqual(purchase, transactions[0].external_payment_response)
        self.assertEqual(purchase['orderId'], transactions[0].external_transaction_id)
        self.assertEqual(payment_methods[0], transactions[0].payment_method)
        self.assertEqual(self.plan, transactions[0].plan)
        self.assertEqual(PaymentTransaction.STATUS_APPROVED, transactions[0].status)
        self.assertEqual(subscriptions[0], transactions[0].subscription)
        self.assertEqual(PaymentTransaction.TYPE_FREE_TRIAL, transactions[0].type)
        self.assertEqual(self.user, transactions[0].user)
        self.assertEqual(0, transactions[0].vat_amount)
        self.assertEqual(0, transactions[0].vat_percentage)
        self.assertEqual(self.currency, transactions[0].currency)
        self.assertEqual(PaymentTransaction.PLATFORM_ANDROID, transactions[0].platform)

        # test analytics
        mocked_segment_new.assert_called_once_with(
            self.user.current_subscription(),
            PlatformType.ANDROID,
            android_user_agent,
            '127.0.0.1',
            self.country.code,
        )

    @responses.activate
    @patch(
        'amuse.api.base.views.subscription.google_subscription.subscription_new_intro_started'
    )
    @patch.object(GooglePlayAPI, 'verify_purchase_token')
    def test_create_introductory_subscription(self, mock_verify, mocked_segment_new):
        expiry_timestamp = 1610645074
        start_timestamp = 1615647910

        purchase = {
            'expiryTimeMillis': str(expiry_timestamp * 1000),
            'startTimeMillis': str(start_timestamp * 1000),
            'priceAmountMicros': '1990000',
            'countryCode': 'FK',
            'priceCurrencyCode': 'FKD',
            'orderId': 'GOOGLE-TEST-SUB-123',
            'paymentState': 1,
            'autoRenewing': True,
            'introductoryPriceInfo': {
                'introductoryPriceCurrencyCode': 'FKD',
                'introductoryPriceAmountMicros': '1980000',
                'introductoryPricePeriod': 'P1Y',
                'introductoryPriceCycles': '1',
            },
        }
        mock_verify.return_value = purchase
        payload = {'google_subscription_id': 'sku_123', 'purchase_token': 'pt_123'}

        android_user_agent = 'amuse-Android/3.12.1; Cellular'
        headers = {'HTTP_USER_AGENT': android_user_agent}
        response = self.client.post(self.url, payload, format='json', **headers)

        # test
        subscriptions = list(Subscription.objects.filter(user=self.user))
        transactions = list(PaymentTransaction.objects.filter(user=self.user))
        payment_methods = list(PaymentMethod.objects.filter(user=self.user))

        self.assertEqual(status.HTTP_201_CREATED, response.status_code)
        self.assertEqual(1, len(subscriptions), 'Subscription is not created')
        self.assertEqual(1, len(payment_methods), 'PaymentMethod is not created')
        self.assertEqual(1, len(transactions), 'Transaction is not created')

        # test payment method
        self.assertEqual('pt_123', payment_methods[0].external_recurring_id)
        self.assertEqual('GOOGL', payment_methods[0].method)

        # test subscription
        self.assertEqual(Subscription.STATUS_ACTIVE, subscriptions[0].status)
        self.assertEqual(Subscription.PROVIDER_GOOGLE, subscriptions[0].provider)
        self.assertEqual(payment_methods[0], subscriptions[0].payment_method)
        self.assertIsNone(subscriptions[0].valid_until)
        self.assertIsNone(subscriptions[0].grace_period_until)

        self.assertIsNone(subscriptions[0].free_trial_from)
        self.assertIsNone(subscriptions[0].free_trial_until)

        # test transaction
        self.assertEqual(Decimal('1.98'), transactions[0].amount)
        self.assertEqual(PaymentTransaction.CATEGORY_INITIAL, transactions[0].category)
        self.assertEqual('FK', transactions[0].country.code)
        self.assertEqual(payload, transactions[0].customer_payment_payload)
        self.assertEqual(purchase, transactions[0].external_payment_response)
        self.assertEqual(purchase['orderId'], transactions[0].external_transaction_id)
        self.assertEqual(payment_methods[0], transactions[0].payment_method)
        self.assertEqual(self.plan, transactions[0].plan)
        self.assertEqual(PaymentTransaction.STATUS_APPROVED, transactions[0].status)
        self.assertEqual(subscriptions[0], transactions[0].subscription)
        self.assertEqual(
            PaymentTransaction.TYPE_INTRODUCTORY_PAYMENT, transactions[0].type
        )
        self.assertEqual(self.user, transactions[0].user)
        self.assertEqual(0, transactions[0].vat_amount)
        self.assertEqual(0, transactions[0].vat_percentage)
        self.assertEqual(self.currency, transactions[0].currency)
        self.assertEqual(PaymentTransaction.PLATFORM_ANDROID, transactions[0].platform)

        # test analytics
        mocked_segment_new.assert_called_once_with(
            self.user.current_subscription(),
            PlatformType.ANDROID,
            android_user_agent,
            '127.0.0.1',
            self.country.code,
        )


class CreateGoogleSubscriptionV2SuccessTestCase(AmuseAPITestCase):
    @responses.activate
    def setUp(self):
        add_zendesk_mock_post_response()
        self.user = UserFactory()
        self.client.force_authenticate(self.user)
        self.client.credentials(HTTP_ACCEPT=API_V5_ACCEPT_VALUE)
        self.plan = SubscriptionPlanFactory(google_product_id='sku_123')
        self.payment_method = PaymentMethodFactory(
            external_recurring_id='pt_123', user=self.user
        )
        self.subscription = SubscriptionFactory(
            user=self.user,
            plan=self.plan,
            payment_method=self.payment_method,
            status=Subscription.STATUS_ACTIVE,
        )
        self.url = reverse('create-google-subscription')

    @responses.activate
    @patch.object(GooglePlayAPI, 'verify_purchase_token')
    def test_successful(self, mock_verify):
        user_id_b64 = base64.b64encode(str(self.user.pk).encode('ascii'))
        mock_verify.return_value = {
            'obfuscatedExternalAccountId': user_id_b64,
            'purchaseToken': 'pt_123',
        }

        payload = {'google_subscription_id': 'sku_123', 'purchase_token': 'pt_123'}
        response = self.client.post(self.url, payload, format='json')

        self.assertEqual(status.HTTP_201_CREATED, response.status_code)


class CreateGoogleSubscriptionV2FailTestCase(AmuseAPITestCase):
    @responses.activate
    def setUp(self):
        add_zendesk_mock_post_response()
        self.user = UserFactory()
        self.client.force_authenticate(self.user)
        self.client.credentials(HTTP_ACCEPT=API_V5_ACCEPT_VALUE)
        self.plan = SubscriptionPlanFactory(google_product_id='sku_123')
        self.payment_method = PaymentMethodFactory(
            external_recurring_id='pt_123', user=self.user
        )
        self.url = reverse('create-google-subscription')

    @responses.activate
    @patch.object(GooglePlayAPI, 'verify_purchase_token')
    def test_subscription_missing(self, mock_verify):
        user_id_b64 = base64.b64encode(str(self.user.pk).encode('ascii'))
        mock_verify.return_value = {
            'obfuscatedExternalAccountId': user_id_b64,
            'purchaseToken': 'pt_123',
        }

        payload = {'google_subscription_id': 'sku_123', 'purchase_token': 'pt_123'}
        response = self.client.post(self.url, payload, format='json')

        self.assertEqual(status.HTTP_400_BAD_REQUEST, response.status_code)
        self.assertIn('purchase_token', response.data)
        self.assertEqual(
            str(response.data['purchase_token']), 'Subscription not created.'
        )

    @responses.activate
    @patch.object(GooglePlayAPI, 'verify_purchase_token')
    def test_multiple_subscriptions(self, mock_verify):
        SubscriptionFactory(
            user=self.user,
            plan=self.plan,
            payment_method=self.payment_method,
            status=Subscription.STATUS_ACTIVE,
        )
        SubscriptionFactory(
            user=self.user,
            plan=self.plan,
            payment_method=self.payment_method,
            status=Subscription.STATUS_ERROR,
        )

        user_id_b64 = base64.b64encode(str(self.user.pk).encode('ascii'))
        mock_verify.return_value = {
            'obfuscatedExternalAccountId': user_id_b64,
            'purchaseToken': 'pt_123',
        }

        payload = {'google_subscription_id': 'sku_123', 'purchase_token': 'pt_123'}
        response = self.client.post(self.url, payload, format='json')

        self.assertEqual(status.HTTP_400_BAD_REQUEST, response.status_code)
        self.assertIn('purchase_token', response.data)
        self.assertEqual(
            str(response.data['purchase_token']),
            'Multiple subscriptions created. Contact support.',
        )

    @responses.activate
    @patch.object(GooglePlayAPI, 'verify_purchase_token')
    def test_fraud_attempt_1(self, mock_verify):
        add_zendesk_mock_post_response()
        user = UserFactory()
        SubscriptionFactory(
            user=user,
            plan=self.plan,
            payment_method=self.payment_method,
            status=Subscription.STATUS_ACTIVE,
        )

        user_id_b64 = base64.b64encode(str(self.user.pk).encode('ascii'))
        mock_verify.return_value = {
            'obfuscatedExternalAccountId': user_id_b64,
            'purchaseToken': 'pt_123',
        }

        payload = {'google_subscription_id': 'sku_123', 'purchase_token': 'pt_123'}
        response = self.client.post(self.url, payload, format='json')

        self.assertEqual(status.HTTP_400_BAD_REQUEST, response.status_code)
        self.assertIn('purchase_token', response.data)
        self.assertEqual(
            str(response.data['purchase_token']),
            'Subscription already created. Possible fraud attempt. Contact support.',
        )

    @responses.activate
    @patch.object(GooglePlayAPI, 'verify_purchase_token')
    def test_fraud_attempt_2(self, mock_verify):
        add_zendesk_mock_post_response()
        user = UserFactory()
        SubscriptionFactory(
            user=self.user,
            plan=self.plan,
            payment_method=self.payment_method,
            status=Subscription.STATUS_ACTIVE,
        )

        user_id_b64 = base64.b64encode(str(user.pk).encode('ascii'))
        mock_verify.return_value = {
            'obfuscatedExternalAccountId': user_id_b64,
            'purchaseToken': 'pt_123',
        }

        payload = {'google_subscription_id': 'sku_123', 'purchase_token': 'pt_123'}
        response = self.client.post(self.url, payload, format='json')

        self.assertEqual(status.HTTP_400_BAD_REQUEST, response.status_code)
        self.assertIn('purchase_token', response.data)
        self.assertEqual(
            str(response.data['purchase_token']),
            'Possible fraud attempt. Contact support.',
        )
