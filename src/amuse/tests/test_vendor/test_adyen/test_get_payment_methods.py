import json
import responses

from amuse.utils import CLIENT_WEB
from amuse.tests.test_vendor.test_adyen.base import AdyenBaseTestCase
from amuse.tests.test_vendor.test_adyen.helpers import mock_payment_methods
from amuse.vendor.adyen import get_payment_methods
from subscriptions.tests.factories import SubscriptionPlanFactory


class GetPaymentMethodsTest(AdyenBaseTestCase):
    @responses.activate
    def test_get_payment_methods(self):
        plan = SubscriptionPlanFactory()
        mock_response = mock_payment_methods()
        responses.add(
            responses.POST,
            'https://checkout-test.adyen.com/v49/paymentMethods',
            json.dumps(mock_response),
            status=200,
        )
        self.assertEqual(get_payment_methods(plan, 'SE', CLIENT_WEB), mock_response)

    @responses.activate
    def test_get_payment_methods_replaces_card_with_credit_card(self):
        plan = SubscriptionPlanFactory()
        mock_response = mock_payment_methods(name='Card')
        expected_response = mock_payment_methods(name='Credit Card')
        responses.add(
            responses.POST,
            'https://checkout-test.adyen.com/v49/paymentMethods',
            json.dumps(mock_response),
            status=200,
        )
        self.assertEqual(get_payment_methods(plan, 'SE', CLIENT_WEB), expected_response)
