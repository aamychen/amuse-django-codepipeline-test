import json
from decimal import Decimal
from unittest import skip
from unittest.mock import patch

import responses
from dateutil.relativedelta import relativedelta
from django.conf import settings
from django.urls import reverse
from django.utils import timezone
from rest_framework import status

from amuse.platform import PlatformType
from amuse.tests.test_api.base import (
    API_V2_ACCEPT_VALUE,
    API_V4_ACCEPT_VALUE,
    AmuseAPITestCase,
)
from amuse.vendor.apple.exceptions import (
    DuplicateAppleSubscriptionError,
    DuplicateAppleTransactionIDError,
    EmptyAppleReceiptError,
    MaxRetriesExceededError,
    UnknownAppleError,
)
from countries.tests.factories import CountryFactory
from payments.models import PaymentTransaction
from payments.tests.factories import PaymentMethodFactory, PaymentTransactionFactory
from subscriptions.tests.factories import SubscriptionFactory, SubscriptionPlanFactory
from subscriptions.tests.helpers import apple_receipt_validation_response
from users.tests.factories import UserFactory


class AppleSubscriptionTestCase(AmuseAPITestCase):
    @responses.activate
    def setUp(self):
        super().setUp()
        self.app_payload = {'receipt_data': '...'}
        self.country = CountryFactory(code='SE')
        self.user = UserFactory(country='US')
        self.client.force_authenticate(self.user)
        self.plan = SubscriptionPlanFactory(
            apple_product_id='amuse_pro_monthly_renewal',
            apple_product_id_notrial='amuse_pro_monthly_renewal_notrial',
        )
        self.url = reverse('create-apple-subscription')
        self.client.credentials(HTTP_ACCEPT=API_V4_ACCEPT_VALUE)
        self.payload = {'receipt_data': 'dummy receipt data'}

    @responses.activate
    @patch('amuse.api.v4.serializers.subscription.subscription_new_started')
    def test_create_sets_user_country_for_payment_transaction_and_returns_201(
        self, mock_new_started
    ):
        country = CountryFactory(code=self.user.country, vat_percentage=Decimal('0.05'))
        self._do_test_create(country, mock_new_started, 'amuse_pro_monthly_renewal')

    @responses.activate
    @patch('amuse.api.v4.serializers.subscription.subscription_new_started')
    def test_create_handles_notrial_plan_and_returns_201(self, mock_new_started):
        country = CountryFactory(code=self.user.country, vat_percentage=Decimal('0.05'))
        self._do_test_create(country, mock_new_started, 'amuse_pro_monthly_renewal')

    @responses.activate
    @patch('amuse.api.v4.serializers.subscription.subscription_new_started')
    def test_create_fallbacks_to_se_for_payment_transaction_when_no_user_country(
        self, mock_new_started
    ):
        self.user.country = ''
        self.user.save()
        self._do_test_create(
            self.country, mock_new_started, 'amuse_pro_monthly_renewal_notrial'
        )

    def _do_test_create(self, country, mock_new_started, product_id):
        apple_subscription_id = 'abc123'
        expires_date = timezone.now() + relativedelta(months=1)
        receipt = apple_receipt_validation_response(
            external_recurring_id=apple_subscription_id,
            expires_date=expires_date,
            product_id=product_id,
        )
        responses.add(
            responses.POST,
            settings.APPLE_VALIDATION_URL,
            json.dumps(receipt),
            status=200,
        )

        response = self.client.post(self.url, self.app_payload, format='json')
        subscription = self.user.current_subscription()
        payment = subscription.latest_payment()

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        self.assertEqual(subscription.valid_from, timezone.now().date())
        self.assertEqual(
            subscription.payment_method.external_recurring_id, apple_subscription_id
        )

        self.assertEqual(
            payment.external_transaction_id,
            receipt['latest_receipt_info'][-1]['transaction_id'],
        )
        self.assertEqual(payment.category, PaymentTransaction.CATEGORY_INITIAL)
        self.assertEqual(payment.platform, PaymentTransaction.PLATFORM_IOS)
        self.assertEqual(payment.customer_payment_payload, self.app_payload)
        if country:
            self.assertEqual(payment.vat_percentage, country.vat_percentage)
            self.assertEqual(payment.country, country)

        mock_new_started.assert_called_once_with(
            subscription, PlatformType.IOS, '', '127.0.0.1'
        )

    @patch(
        'amuse.api.v4.serializers.subscription.AppleReceiptValidationAPIClient.validate_receipt'
    )
    @patch(
        'amuse.api.v4.serializers.subscription.AppleReceiptValidationAPIClient.get_original_transaction_id'
    )
    def test_invalid_receipt_returns_400_when_original_transaction_id_is_invalid(
        self, mocked_get_original_transaction_id, mocked_validate_receipt
    ):
        mocked_get_original_transaction_id.side_effect = (
            DuplicateAppleSubscriptionError()
        )

        response = self.client.post(self.url, self.app_payload, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    @patch(
        'amuse.api.v4.serializers.subscription.AppleReceiptValidationAPIClient.validate_receipt'
    )
    @patch(
        'amuse.api.v4.serializers.subscription.AppleReceiptValidationAPIClient.get_original_transaction_id'
    )
    @patch(
        'amuse.api.v4.serializers.subscription.AppleReceiptValidationAPIClient.get_transaction_id'
    )
    def test_invalid_receipt_returns_400_when_transaction_id_is_invalid(
        self,
        mocked_get_transaction_id,
        mocked_get_original_transaction_id,
        mocked_validate_receipt,
    ):
        mocked_get_transaction_id.side_effect = DuplicateAppleTransactionIDError()

        response = self.client.post(self.url, self.app_payload, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    @patch(
        'amuse.api.v4.serializers.subscription.AppleReceiptValidationAPIClient.validate_receipt'
    )
    def test_invalid_receipt_returns_400_when_empty_apple_receipt_error_is_raised(
        self, mocked_validate_receipt
    ):
        mocked_validate_receipt.side_effect = EmptyAppleReceiptError(
            'An Empty receipt was received'
        )

        response = self.client.post(self.url, self.app_payload, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    @patch(
        'amuse.api.v4.serializers.subscription.AppleReceiptValidationAPIClient.validate_receipt'
    )
    def test_invalid_receipt_returns_500_when_max_retries_exceeded_error_is_raised(
        self, mocked_validate_receipt
    ):
        mocked_validate_receipt.side_effect = MaxRetriesExceededError(
            'Maximum retries of 3 excceeded, giving up'
        )

        response = self.client.post(self.url, self.app_payload, format='json')

        self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)

    @patch(
        'amuse.api.v4.serializers.subscription.AppleReceiptValidationAPIClient.validate_receipt'
    )
    def test_invalid_receipt_returns_500_when_unknown_apple_error_is_raised(
        self, mocked_validate_receipt
    ):
        mocked_validate_receipt.side_effect = UnknownAppleError(
            'Validate receipt failed with apple server status 2000'
        )

        response = self.client.post(self.url, self.app_payload, format='json')

        self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)

    def test_create_subscription_returns_403_for_frozen_user(self):
        # SubscriptionFactory(user=self.user, plan=self.plan)
        self.user.is_frozen = True
        self.user.save()
        self.user.refresh_from_db()

        response = self.client.post(self.url, self.payload)

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_create_subscription_returns_403_for_already_pro_user(self):
        SubscriptionFactory(user=self.user, plan=self.plan)

        response = self.client.post(self.url, self.payload)

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    @patch('amuse.api.v4.serializers.subscription.uuid4')
    @responses.activate
    def test_only_one_amuse_subscription_per_apple_id(self, mocked_uuid4):
        request_id = '29860639-f17e-4594-9839-8317287a7b22'
        mocked_uuid4.return_value.__str__.return_value = request_id

        apple_subscription_id = 'replay'
        payment_method = PaymentMethodFactory(
            external_recurring_id=apple_subscription_id, method='AAPL'
        )
        previous_signup = PaymentTransactionFactory(
            payment_method=payment_method, subscription__payment_method=payment_method
        )
        expires_date = timezone.now() + relativedelta(months=1)
        responses.add(
            responses.POST,
            settings.APPLE_VALIDATION_URL,
            json.dumps(
                apple_receipt_validation_response(
                    external_recurring_id=apple_subscription_id,
                    expires_date=expires_date,
                )
            ),
            status=200,
        )

        response = self.client.post(self.url, self.payload)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(
            response.json()['non_field_errors'][0],
            'Active subscription with same original_transaction_id exist',
        )
