from datetime import timedelta

import responses
from django.test import TestCase, override_settings
from django.utils import timezone

from amuse.tests.helpers import (
    ZENDESK_MOCK_API_URL_TOKEN,
    add_zendesk_mock_post_response,
)
from payments.tests.factories import PaymentMethodFactory, PaymentTransactionFactory
from subscriptions.models import Subscription
from subscriptions.tests.factories import SubscriptionFactory


@override_settings(**ZENDESK_MOCK_API_URL_TOKEN)
class PaymentTransactionTestCase(TestCase):
    @responses.activate
    def test_payment_transaction_external_url(self):
        add_zendesk_mock_post_response()
        ios_subscription = SubscriptionFactory(provider=Subscription.PROVIDER_IOS)
        ios_transaction = PaymentTransactionFactory(subscription=ios_subscription)
        adyen_id = 'data9000'
        adyen_transaction = PaymentTransactionFactory(external_transaction_id=adyen_id)

        assert ios_transaction.external_url() is None
        assert adyen_id in adyen_transaction.external_url()

    @responses.activate
    def test_adyen_amount_formmated(self):
        add_zendesk_mock_post_response()
        tx = PaymentTransactionFactory(amount=10)
        decimals = tx.currency.decimals
        self.assertEqual(
            int(tx.amount * pow(10, decimals)), tx.get_amount_formatted_adyen
        )


@override_settings(**ZENDESK_MOCK_API_URL_TOKEN)
class PaymentMethodTestCase(TestCase):
    @responses.activate
    def test_is_expired(self):
        add_zendesk_mock_post_response()
        expired_method = PaymentMethodFactory(
            expiry_date=timezone.now().date() - timedelta(days=10)
        )
        active_method = PaymentMethodFactory(
            expiry_date=timezone.now().date() + timedelta(days=10)
        )

        assert expired_method.is_expired()
        assert not active_method.is_expired()
