from datetime import date, datetime, timezone
from unittest.mock import patch

from django.conf import settings
from django.test import override_settings

from amuse.tests.test_vendor.test_adyen.base import AdyenBaseTestCase
from amuse.vendor.adyen.helpers import (
    convert_to_end_of_the_day,
    get_adyen_client,
    get_or_create_payment_method,
)
from payments.models import PaymentMethod
from payments.tests.factories import PaymentMethodFactory
from users.tests.factories import UserFactory


def test_convert_to_end_of_the_day():
    _date = date(2020, 2, 25)
    assert convert_to_end_of_the_day(_date) == datetime(
        2020, 2, 25, 23, 59, 59, tzinfo=timezone.utc
    )


@patch('amuse.vendor.adyen.helpers.Adyen.Adyen')
def test_get_adyen_client_test(mocked_adyen):
    get_adyen_client()
    mocked_adyen.assert_called_once_with(
        app_name='Amuse.io',
        xapikey=settings.ADYEN_API_KEY,
        platform=settings.ADYEN_PLATFORM,
    )


@patch('amuse.vendor.adyen.helpers.Adyen.Adyen')
@override_settings(ADYEN_LIVE_ENDPOINT_PREFIX='blahonga', ADYEN_PLATFORM='live')
def test_get_adyen_client_prod(mocked_adyen):
    get_adyen_client()
    mocked_adyen.assert_called_once_with(
        app_name='Amuse.io',
        live_endpoint_prefix='blahonga',
        platform='live',
        xapikey=settings.ADYEN_API_KEY,
    )


class GetPaymentMethodsTest(AdyenBaseTestCase):
    @patch('amuse.vendor.zendesk.api.create_or_update_user')
    def test_multiple_payment_methods(self, mock_zendesk):
        method_data = {
            'external_recurring_id': '123',
            'method': 'visapal',
            'summary': None,
            'expiry_date': None,
        }

        user = UserFactory()
        method1 = PaymentMethodFactory(
            user=user,
            external_recurring_id=method_data['external_recurring_id'],
            method=method_data['method'],
            summary=method_data['summary'],
            expiry_date=method_data['expiry_date'],
        )
        method2 = PaymentMethodFactory(
            user=user,
            external_recurring_id=method_data['external_recurring_id'],
            method=method_data['method'],
            summary=method_data['summary'],
            expiry_date=method_data['expiry_date'],
        )

        response = {
            'additionalData': {
                'paymentMethod': method_data['method'],
                'cardSummary': method_data['summary'],
                'recurring.recurringDetailReference': method_data[
                    'external_recurring_id'
                ],
            }
        }

        fetched_method = get_or_create_payment_method(user, response)
        self.assertEqual(PaymentMethod.objects.count(), 2)
        self.assertEqual(fetched_method, method1)

    @patch('amuse.vendor.zendesk.api.create_or_update_user')
    def test_create_payment_method(self, mock_zendesk):
        method_data = {
            'external_recurring_id': '123',
            'method': 'visapal',
            'summary': None,
            'expiry_date': None,
        }

        user = UserFactory()
        method1 = PaymentMethodFactory(
            external_recurring_id=method_data['external_recurring_id'],
            method=method_data['method'],
            summary=method_data['summary'],
            expiry_date=method_data['expiry_date'],
        )

        response = {
            'additionalData': {
                'paymentMethod': method_data['method'],
                'cardSummary': method_data['summary'],
                'recurring.recurringDetailReference': method_data[
                    'external_recurring_id'
                ],
            }
        }

        fetched_method = get_or_create_payment_method(user, response)
        self.assertEqual(PaymentMethod.objects.count(), 2)
        self.assertNotEqual(method1, fetched_method)
        self.assertEqual(fetched_method.user, user)
        self.assertEqual(
            fetched_method.external_recurring_id, method_data['external_recurring_id']
        )
        self.assertEqual(fetched_method.method, method_data['method'])
        self.assertEqual(fetched_method.summary, method_data['summary'])
        self.assertEqual(fetched_method.expiry_date, method_data['expiry_date'])
