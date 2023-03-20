from decimal import Decimal
from unittest.mock import patch

import responses
from django.urls import reverse
from rest_framework import status

from amuse.platform import PlatformType
from amuse.tests.test_api.base import (
    API_V2_ACCEPT_VALUE,
    API_V4_ACCEPT_VALUE,
    AmuseAPITestCase,
)
from amuse.tests.test_vendor.test_adyen.base import AdyenBaseTestCase
from payments.models import PaymentTransaction
from payments.tests.factories import PaymentTransactionFactory
from subscriptions.models import Subscription
from subscriptions.tests.factories import SubscriptionFactory
from users.tests.factories import UserFactory


class PaymentTransactionTestCase(AmuseAPITestCase):
    def setUp(self):
        self.user = UserFactory()
        self.transaction = PaymentTransactionFactory(
            user=self.user, vat_amount=Decimal("1.00")
        )
        self.other_transaction = PaymentTransactionFactory()
        self.url = reverse('payment-transactions')
        self.client.credentials(HTTP_ACCEPT=API_V4_ACCEPT_VALUE)
        self.client.force_authenticate(self.user)

    def test_only_own_transactions_visible(self):
        payload = self.client.get(self.url).json()

        self.assertEqual(len(payload), 1)
        p = payload[0]
        self.assertEqual(p['id'], self.transaction.pk)
        self.assertEqual(p['country']['code'], self.transaction.country.code)
        self.assertEqual(
            p['subscription']['plan']['id'], self.transaction.subscription.plan_id
        )
        self.assertEqual(p['amount'], str(self.transaction.amount))
        self.assertEqual(p['currency'], self.transaction.get_currency_display())
        self.assertEqual(p['vat_amount'], str(self.transaction.vat_amount))
        self.assertEqual(
            Decimal(p['vat_percentage']), Decimal(self.transaction.vat_percentage)
        )
        self.assertEqual(
            p['external_transaction_id'], self.transaction.external_transaction_id
        )
        self.assertEqual(p['type'], self.transaction.get_type_display())

    def test_auth_transactions_visible(self):
        auth_payment = PaymentTransactionFactory(
            user=self.user, type=PaymentTransaction.TYPE_AUTHORISATION
        )
        payload = self.client.get(self.url).json()

        self.assertEqual(len(payload), 2)
        self.assertEqual(payload[0]['id'], auth_payment.pk)
        self.assertEqual(payload[1]['id'], self.transaction.pk)

    def test_requires_logged_in_user(self):
        self.client.logout()
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_wrong_api_version_return_400(self):
        self.client.credentials(HTTP_ACCEPT=API_V2_ACCEPT_VALUE)

        response = self.client.post(self.url, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.json(), {'detail': 'API version is not supported.'})


class UpdatePaymentTransactionTestCase(AmuseAPITestCase, AdyenBaseTestCase):
    def setUp(self):
        super().setUp()
        self.subscription = SubscriptionFactory(status=Subscription.STATUS_CREATED)
        self.payment = PaymentTransactionFactory(
            subscription=self.subscription, user=self.subscription.user
        )
        self.url = reverse(
            'update-payment-transaction', kwargs={'transaction_id': self.payment.pk}
        )
        self.user = self.payment.user
        self.client.force_authenticate(self.user)
        self.client.credentials(HTTP_ACCEPT=API_V4_ACCEPT_VALUE)

    @responses.activate
    @patch('amuse.api.base.views.payment_transactions.subscription_new_started')
    def test_3ds_details_provided_performs_checkout_and_returns_201(
        self, mocked_subscription_new_started
    ):
        self._add_checkout_response('Authorised', endpoint='payments/details')
        payload = {'MD': '...', 'PaRes': '...'}

        response = self.client.patch(self.url, json=payload)
        self.subscription.refresh_from_db()

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(self.subscription.status, Subscription.STATUS_ACTIVE)
        self.assertTrue(response.json()['is_success'])
        mocked_subscription_new_started.assert_called_once_with(
            self.subscription,
            PlatformType.UNKNOWN,
            '',
            '127.0.0.1',
            self.subscription.latest_payment().currency.code,
        )

    @responses.activate
    @patch(
        'amuse.api.base.views.payment_transactions.subscription_payment_method_changed'
    )
    def test_3ds_checkout_segment_payment_method_change_if_earlier_transaction_exists(
        self, mocked_segment
    ):
        PaymentTransactionFactory(subscription=self.subscription)
        self._add_checkout_response('Authorised', endpoint='payments/details')
        payload = {'MD': '...', 'PaRes': '...'}

        response = self.client.patch(self.url, json=payload)
        self.subscription.refresh_from_db()

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(self.subscription.status, Subscription.STATUS_ACTIVE)
        self.assertTrue(response.json()['is_success'])
        mocked_segment.assert_called_once_with(self.subscription, '', '127.0.0.1')

    @responses.activate
    @patch('amuse.api.base.views.payment_transactions.subscription_new_started')
    def test_3ds_checkout_segment_new_subscription_if_user_has_expired_subscription(
        self, mocked_subscription_new_started
    ):
        expired_subscription = SubscriptionFactory(
            status=Subscription.STATUS_EXPIRED, user=self.user
        )
        self._add_checkout_response('Authorised', endpoint='payments/details')
        payload = {'MD': '...', 'PaRes': '...'}

        response = self.client.patch(self.url, json=payload)
        self.subscription.refresh_from_db()

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(self.subscription.status, Subscription.STATUS_ACTIVE)
        self.assertTrue(response.json()['is_success'])
        mocked_subscription_new_started.assert_called_once_with(
            self.subscription,
            PlatformType.UNKNOWN,
            '',
            '127.0.0.1',
            self.subscription.latest_payment().currency.code,
        )
