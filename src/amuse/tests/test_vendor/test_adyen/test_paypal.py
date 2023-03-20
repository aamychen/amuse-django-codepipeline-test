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
from countries.tests.factories import CountryFactory
from payments.models import PaymentTransaction
from payments.tests.factories import PaymentTransactionFactory
from subscriptions.models import Subscription
from subscriptions.tests.factories import SubscriptionPlanFactory, SubscriptionFactory
from users.tests.factories import UserFactory


@override_settings(
    ADYEN_NOTIFICATION_HMAC='1337',
    ADYEN_NOTIFICATION_PASSWORD='test',
    ADYEN_NOTIFICATION_USER='test',
    **ZENDESK_MOCK_API_URL_TOKEN,
)
class PayPalTestCase(AdyenBaseTestCase):
    @responses.activate
    def setUp(self):
        add_zendesk_mock_post_response()
        self.user = UserFactory()
        self.plan = SubscriptionPlanFactory(trial_days=0)
        self.country = CountryFactory(code='US')
        self.headers = self._get_auth_header(
            settings.ADYEN_NOTIFICATION_USER, settings.ADYEN_NOTIFICATION_PASSWORD
        )
        self.dummy_ip = '127.0.0.1'
        self.dummy_browser_info = {'sent': 'to adyen'}

    def _get_auth_header(self, username, password):
        auth = base64.b64encode(f'{username}:{password}'.encode()).decode()
        return {'HTTP_AUTHORIZATION': f'Basic {auth}'}

    @responses.activate
    @patch(
        'payments.views.AdyenNotificationView._is_valid_payload_hmac', return_value=True
    )
    def test_new_subscription_flow(self, mock_hmac):
        # step 1: paypal flow is initiated, return the 'action'
        self._add_checkout_paypal()
        response = create_subscription(
            self.user,
            self.plan,
            mock_payment_details(),
            self.country,
            CLIENT_WEB,
            ip=None,
            browser_info=None,
        )

        self.assertFalse(response['is_success'])
        self.assertEqual(response['action'], self.mock_response['action'])
        payment = PaymentTransaction.objects.last()
        self.assertEqual(response['transaction_id'], payment.pk)
        # pending payments have no external transaction ID
        self.assertEqual(payment.external_transaction_id, '')
        self.assertEqual(Subscription.objects.count(), 1)
        self.assertEqual(payment.subscription.plan_id, self.plan.pk)
        self.assertEqual(payment.status, PaymentTransaction.STATUS_NOT_SENT)
        self.assertEqual(payment.subscription.user_id, self.user.pk)
        self.assertEqual(payment.subscription.status, Subscription.STATUS_CREATED)

        # step 2: additional data is sent to complete the payment process
        data = {'additional': 'data'}
        self._add_checkout_paypal(result_code='Authorised', endpoint='payments/details')
        response = authorise_3ds(data, payment)

        payment.refresh_from_db()
        self.assertTrue(response['is_success'])
        self.assertEqual(payment.subscription.status, Subscription.STATUS_ACTIVE)
        self.assertEqual(payment.status, PaymentTransaction.STATUS_APPROVED)
        self.assertEqual(payment.payment_method.method, 'paypal')
        self.assertEqual(payment.payment_method.user, self.user)
        self.assertEqual(payment.external_payment_response, self.mock_response)
        self.assertEqual(
            payment.external_transaction_id, self.mock_response['pspReference']
        )

        # step 3: notification listener to get recurring ID
        recurring_id = str(uuid.uuid4())
        data = {
            "live": "false",
            "notificationItems": [
                {
                    "NotificationRequestItem": {
                        "additionalData": {
                            "issuerCountry": "US",
                            "recurring.recurringDetailReference": recurring_id,
                            "recurring.shopperReference": "140956",
                        },
                        "amount": {"currency": "EUR", "value": 2000},
                        "eventCode": "AUTHORISATION",
                        "eventDate": "2019-12-16T11:42:12+01:00",
                        "merchantAccountCode": settings.ADYEN_MERCHANT_ACCOUNT,
                        "merchantReference": str(payment.pk),
                        "paymentMethod": 'paypal',
                        "pspReference": payment.external_transaction_id,
                        "reason": "",
                        "success": "true",
                    }
                }
            ],
        }

        payment.payment_method = None
        payment.save()
        response = self.client.post(
            reverse('adyen-notifications'),
            json.dumps(data),
            content_type='application/json',
            **self.headers,
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        payment.refresh_from_db()
        self.assertEqual(payment.payment_method.external_recurring_id, recurring_id)
        self.assertEqual(payment.payment_method.method, 'paypal')

    @patch(
        'payments.views.AdyenNotificationView._is_valid_payload_hmac', return_value=True
    )
    @responses.activate
    def test_update_payment_method_flow(self, mock_hmac):
        subscription = SubscriptionFactory(user=self.user, plan=self.plan)
        payment = PaymentTransactionFactory(
            user=self.user,
            plan=self.plan,
            subscription=subscription,
            payment_method=subscription.payment_method,
        )
        self.assertTrue(self.user.is_pro)

        # step 1: authorization of new payment method
        self._add_checkout_paypal()
        response = authorise_payment_method(
            self.user,
            mock_payment_details(),
            self.country,
            CLIENT_WEB,
            ip=self.dummy_ip,
            browser_info=self.dummy_browser_info,
        )

        self.assertFalse(response['is_success'])
        self.assertEqual(response['action'], self.mock_response['action'])
        payment = PaymentTransaction.objects.last()
        self.assertEqual(response['transaction_id'], payment.pk)
        # pending payments have no external transaction ID
        self.assertEqual(payment.external_transaction_id, '')
        self.assertEqual(Subscription.objects.count(), 1)
        self.assertEqual(payment.subscription.plan_id, self.plan.pk)
        self.assertEqual(payment.status, PaymentTransaction.STATUS_NOT_SENT)
        self.assertEqual(payment.subscription.user_id, self.user.pk)
        self.assertEqual(payment.subscription.status, Subscription.STATUS_ACTIVE)
        self.assertEqual(payment.type, PaymentTransaction.TYPE_AUTHORISATION)

        # step 2: additional data is sent to complete the payment process
        data = {'additional': 'data'}
        self._add_checkout_paypal(result_code='Authorised', endpoint='payments/details')
        response = authorise_3ds(data, payment)

        payment.refresh_from_db()
        self.assertTrue(response['is_success'])
        self.assertEqual(payment.subscription.status, Subscription.STATUS_ACTIVE)
        self.assertEqual(payment.status, PaymentTransaction.STATUS_APPROVED)
        self.assertEqual(payment.payment_method.method, 'paypal')
        self.assertEqual(payment.payment_method.user, self.user)
        self.assertEqual(payment.external_payment_response, self.mock_response)
        self.assertEqual(
            payment.external_transaction_id, self.mock_response['pspReference']
        )

        # step 3: notification listener to get recurring ID
        recurring_id = str(uuid.uuid4())
        data = {
            "live": "false",
            "notificationItems": [
                {
                    "NotificationRequestItem": {
                        "additionalData": {
                            "issuerCountry": "US",
                            "recurring.recurringDetailReference": recurring_id,
                            "recurring.shopperReference": "140956",
                        },
                        "amount": {"currency": "EUR", "value": 2000},
                        "eventCode": "AUTHORISATION",
                        "eventDate": "2019-12-16T11:42:12+01:00",
                        "merchantAccountCode": settings.ADYEN_MERCHANT_ACCOUNT,
                        "merchantReference": str(payment.pk),
                        "paymentMethod": 'paypal',
                        "pspReference": payment.external_transaction_id,
                        "reason": "",
                        "success": "true",
                    }
                }
            ],
        }

        payment.payment_method = None
        payment.save()
        response = self.client.post(
            reverse('adyen-notifications'),
            json.dumps(data),
            content_type='application/json',
            **self.headers,
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        payment.refresh_from_db()
        self.assertEqual(payment.payment_method.external_recurring_id, recurring_id)
        self.assertEqual(payment.payment_method.method, 'paypal')
