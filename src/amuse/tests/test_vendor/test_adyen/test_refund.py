import base64
import json
import uuid
from unittest.mock import patch

import responses
from django.conf import settings
from django.test import override_settings
from rest_framework import status
from rest_framework.reverse import reverse

from amuse.tests.helpers import (
    add_zendesk_mock_post_response,
    ZENDESK_MOCK_API_URL_TOKEN,
)
from amuse.tests.test_vendor.test_adyen.base import AdyenBaseTestCase
from amuse.tests.test_vendor.test_adyen.helpers import mock_payment_details
from amuse.utils import CLIENT_WEB
from amuse.vendor.adyen import (
    create_subscription,
    authorise_3ds,
    authorise_payment_method,
)
from countries.tests.factories import CountryFactory, CurrencyFactory
from payments.models import PaymentTransaction
from payments.tests.factories import PaymentTransactionFactory
from subscriptions.models import Subscription
from subscriptions.tests.factories import SubscriptionPlanFactory, SubscriptionFactory
from users.tests.factories import UserFactory
from amuse.vendor.adyen.base import AdyenRefund


@override_settings(
    **ZENDESK_MOCK_API_URL_TOKEN,
)
class AdyenRefundTestCase(AdyenBaseTestCase):
    @responses.activate
    def setUp(self):
        add_zendesk_mock_post_response()
        self.user = UserFactory()
        self.plan = SubscriptionPlanFactory(trial_days=0)
        self.payment = PaymentTransactionFactory(
            amount=50,
            plan=self.plan,
            user=self.user,
        )

    @responses.activate
    def test_refund_call_success(self):
        country = self.payment.country
        price_card = self.payment.plan.get_price_card(country.code)

        responses.add(
            responses.POST,
            "https://pal-test.adyen.com/pal/servlet/Payment/v49/refund",
            json.dumps(
                {
                    'pspReference': '862618593929080C',
                    'response': '[refund-received]',
                }
            ),
            status=200,
        )

        refund_executor = AdyenRefund(self.payment)
        payload = refund_executor._get_refund_payload()
        self.assertEqual(
            payload['originalReference'], self.payment.external_transaction_id
        )
        self.assertEqual(payload['reference'], self.payment.pk)
        self.assertEqual(
            payload['modificationAmount']['value'],
            self.payment.get_amount_formatted_adyen,
        )
        return_value = refund_executor.refund()
        self.assertTrue(return_value['is_success'])

    @patch('amuse.vendor.adyen.base.logger')
    def test_refund_call_failed(self, mock_logger):
        refund_executor = AdyenRefund(self.payment)
        return_value = refund_executor.refund()
        self.assertFalse(return_value['is_success'])
        mock_logger.error.assert_called_once_with(
            f"Error executing Adyen refund for payment_id {self.payment.pk} error=Tests must mock all HTTP requests!"
        )

    @responses.activate
    @patch('amuse.vendor.adyen.base.logger')
    def test_adyen_error_handler(self, mock_logger):
        responses.add(
            responses.POST,
            "https://pal-test.adyen.com/pal/servlet/Payment/v49/refund",
            json.dumps(
                {
                    "status": 422,
                    "errorCode": "167",
                    "message": "Original pspReference required for this operation",
                    "errorType": "validation",
                }
            ),
            status=442,
        )
        refund_executor = AdyenRefund(self.payment)
        return_value = refund_executor.refund()
        self.assertFalse(return_value['is_success'])
        mock_logger.error.assert_called_once()
