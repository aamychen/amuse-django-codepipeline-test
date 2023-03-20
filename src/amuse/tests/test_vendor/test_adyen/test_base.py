from unittest.mock import Mock, patch

from django.test import TestCase

from amuse.utils import CLIENT_ANDROID
from amuse.vendor.adyen.base import Adyen3DS, AdyenBase, AdyenSubscription
from payments.tests.factories import PaymentTransactionFactory
from subscriptions.tests.factories import SubscriptionPlanFactory
from users.tests.factories import UserFactory


class AdyenBaseTestCase(TestCase):
    def test_get_endpoint_callable_raises_not_implemented_error(self):
        adyen_client = AdyenBase()
        with self.assertRaises(NotImplementedError):
            adyen_client._get_endpoint_callable()

    def test_get_endpoint_callable_returns_adyen_subcription_endpoint_callable(self):
        mocked_user = Mock()
        adyen_client = AdyenSubscription(mocked_user)
        self.assertEqual(
            adyen_client._get_endpoint_callable(), adyen_client.client.checkout.payments
        )

    def test_get_endpoint_callable_returns_adyen_3ds_endpoint_callable(self):
        adyen_client = Adyen3DS()
        self.assertEqual(
            adyen_client._get_endpoint_callable(),
            adyen_client.client.checkout.payments_details,
        )

    @patch('amuse.tasks.zendesk_create_or_update_user')
    def test_3d_secure_extra_data_android_client_does_not_include_origin(
        self, mock_zendesk
    ):
        user = UserFactory()
        plan = SubscriptionPlanFactory()
        payment = PaymentTransactionFactory(user=user)
        adyen_client = AdyenSubscription(
            user, client=CLIENT_ANDROID, subscription_plan=plan
        )
        self.assertEqual(adyen_client.channel, 'Android')
        assert 'origin' not in adyen_client._get_authorise_payload(
            {}, payment, is_3d_secure=True
        )

    @patch('amuse.tasks.zendesk_create_or_update_user')
    def test_3d_secure_extra_data_web_client_includes_origin(self, mock_zendesk):
        user = UserFactory()
        payment = PaymentTransactionFactory(user=user)
        plan = SubscriptionPlanFactory()
        adyen_client = AdyenSubscription(user, subscription_plan=plan)
        self.assertEqual(adyen_client.channel, 'Web')
        assert 'origin' in adyen_client._get_authorise_payload(
            {}, payment, is_3d_secure=True
        )
