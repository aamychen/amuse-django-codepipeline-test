import json
from datetime import timedelta

import responses
from django.test import TestCase, override_settings

from amuse.tests.helpers import ZENDESK_MOCK_API_URL_TOKEN
from amuse.tests.test_vendor.test_adyen.helpers import (
    mock_country_check_response,
    mock_payment_redirect,
    mock_payment_response,
    mock_payment_paypal,
)
from payments.models import PaymentTransaction
from subscriptions.models import Subscription


@override_settings(**ZENDESK_MOCK_API_URL_TOKEN)
class AdyenBaseTestCase(TestCase):
    def _add_checkout_response(
        self,
        result_code,
        endpoint="payments",
        additional_data=None,
        is_renewal=False,
        refusal_reason=None,
    ):
        response = mock_payment_response(
            self.user,
            result_code=result_code,
            additional_data=additional_data,
            is_renewal=is_renewal,
            refusal_reason=refusal_reason,
        )
        self.mock_response = response
        responses.add(
            responses.POST,
            "https://checkout-test.adyen.com/v49/" + endpoint,
            json.dumps(response),
            status=200,
        )

    def _add_checkout_redirect(self):
        response = mock_payment_redirect()
        self.mock_response = response
        responses.add(
            responses.POST,
            "https://checkout-test.adyen.com/v49/payments",
            json.dumps(response),
            status=200,
        )

    def _add_checkout_paypal(
        self, endpoint="payments", result_code="Pending", include_payment_method=True
    ):
        response = mock_payment_paypal(result_code, include_payment_method)
        self.mock_response = response
        responses.add(
            responses.POST,
            f"https://checkout-test.adyen.com/v49/{endpoint}",
            json.dumps(response),
            status=200,
        )

    def _add_error_response(self, external_payment_id="123"):
        adyen_raw_response = '{"status":422,"errorCode":"14_007","message":"Invalid payment method data","errorType":"validation"}'
        responses.add(
            responses.POST,
            "https://checkout-test.adyen.com/v49/payments",
            adyen_raw_response,
            headers={"pspReference": external_payment_id},
            status=422,
        )

    def _add_country_check_response(
        self, country_code=None, response=None, status_code=200
    ):
        if response is None:
            response = json.dumps(mock_country_check_response(country_code))
        responses.add(
            responses.POST,
            'https://pal-test.adyen.com/pal/servlet/BinLookup/v50/getCostEstimate',
            response,
            status=status_code,
        )

    def _assert_payment_and_subscription(
        self,
        payment_status,
        subscription_user_id,
        subscription_status,
        payment_transaction_type=PaymentTransaction.TYPE_PAYMENT,
        is_renewal=False,
    ):
        payment = PaymentTransaction.objects.last()
        self.assertEqual(
            payment.external_transaction_id, self.mock_response["pspReference"]
        )
        if payment_status == PaymentTransaction.STATUS_APPROVED and not is_renewal:
            self.assertEqual(
                payment.subscription.payment_method.external_recurring_id,
                self.mock_response["additionalData"][
                    "recurring.recurringDetailReference"
                ],
            )
        self.assertEqual(payment.subscription.plan_id, self.plan.pk)
        self.assertEqual(payment.status, payment_status)
        self.assertEqual(payment.subscription.user_id, subscription_user_id)
        self.assertEqual(payment.subscription.status, subscription_status)
        self.assertEqual(payment.vat_percentage, payment.country.vat_percentage)
