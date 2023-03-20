import json
import uuid
from unittest.mock import patch

import responses
from django.conf import settings
from django.core.signing import TimestampSigner
from django.test import TestCase, override_settings
from django.urls import reverse
from rest_framework import status

from amuse.platform import PlatformType
from amuse.tests.helpers import (
    ZENDESK_MOCK_API_URL_TOKEN,
    add_zendesk_mock_post_response,
    build_auth_header,
)
from amuse.tests.test_vendor.test_adyen.base import AdyenBaseTestCase
from amuse.tokens import payment_success_token_generator
from payments.models import PaymentTransaction, PaymentMethod
from payments.tests.factories import PaymentTransactionFactory
from payments.tests.helpers import adyen_notification
from payments.views import AdyenNotificationView, _send_subscription_new_started_event
from subscriptions.models import Subscription
from subscriptions.tests.factories import SubscriptionPlanFactory
from users.tests.factories import UserFactory


@override_settings(**ZENDESK_MOCK_API_URL_TOKEN)
class AdyenDebugTest(TestCase):
    @responses.activate
    def setUp(self):
        add_zendesk_mock_post_response()
        self.user = UserFactory(is_staff=True)
        self.client.force_login(self.user)
        self.url = reverse('adyen_debug')
        SubscriptionPlanFactory()

    def test_staff_can_access(self):
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertIn(settings.ADYEN_ORIGIN_KEY, response.rendered_content)

    def test_non_staff_not_allowed(self):
        self.user.is_staff = False
        self.user.save()

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 302)


@override_settings(
    ADYEN_NOTIFICATION_HMAC='1337',
    ADYEN_NOTIFICATION_PASSWORD='test',
    ADYEN_NOTIFICATION_USER='test',
    **ZENDESK_MOCK_API_URL_TOKEN,
)
class AdyenNotificationTestCase(TestCase):
    @responses.activate
    def setUp(self):
        add_zendesk_mock_post_response()
        self.payment = PaymentTransactionFactory()
        self.user = self.payment.user
        self.item_data = adyen_notification(
            merchant_account=settings.ADYEN_MERCHANT_ACCOUNT,
            payment_id=self.payment.external_transaction_id,
            user_id=self.user.pk,
        )
        self.data = {'notificationItems': [self.item_data]}
        self.view = AdyenNotificationView()
        self.url = reverse('adyen-notifications')
        self.headers = build_auth_header(
            settings.ADYEN_NOTIFICATION_USER, settings.ADYEN_NOTIFICATION_PASSWORD
        )

    @patch('payments.views.logger.warning')
    def test_wrong_merchant_account_logs_warning(self, mocked_logger):
        self.item_data['NotificationRequestItem'][
            'merchantAccountCode'
        ] = 'wrong account'

        self.assertFalse(self.view._is_valid_merchant_account(self.data))
        mocked_logger.assert_called_once_with(
            'Adyen Merchant Account mismatch, '
            'received: wrong account, '
            f'configured for: {settings.ADYEN_MERCHANT_ACCOUNT}'
        )

    def test_valid_merchant_account_returns_true(self):
        self.item_data['NotificationRequestItem'][
            'merchantAccountCode'
        ] = settings.ADYEN_MERCHANT_ACCOUNT

        self.assertTrue(self.view._is_valid_merchant_account(self.data))

    @patch('payments.views.logger.warning')
    def test_forged_hmac_logs_warning_and_returns_401(self, mocked_logger):
        response = self.client.post(
            self.url,
            json.dumps(self.data),
            content_type='application/json',
            **self.headers,
        )

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        mocked_logger.assert_called_once_with(
            f"Adyen endpoint received invalid HMAC signature for item {self.item_data['NotificationRequestItem']}"
        )

    def test_wrong_http_authorization_returns_401(self):
        headers = build_auth_header('h4x0r', 'k1dd13')
        response = self.client.post(
            self.url, json.dumps(self.data), content_type='application/json', **headers
        )

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    @override_settings(
        ADYEN_NOTIFICATION_HMAC='44782DEF547AAA06C910C43932B1EB0C71FC68D9D0C057550C48EC2ACF6BA056'
    )
    def test_validate_hmac(self):
        payload = {
            "live": "false",
            "notificationItems": [
                {
                    "NotificationRequestItem": {
                        "additionalData": {
                            "hmacSignature": "coqCmt/IZ4E3CzPvMY8zTjQVL5hYJUiBRg8UU+iCWo0="
                        },
                        "amount": {"value": 1130, "currency": "EUR"},
                        "pspReference": "7914073381342284",
                        "eventCode": "AUTHORISATION",
                        "eventDate": "2019-05-06T17:15:34.121+02:00",
                        "merchantAccountCode": "TestMerchant",
                        "operations": ["CANCEL", "CAPTURE", "REFUND"],
                        "merchantReference": "TestPayment-1407325143704",
                        "paymentMethod": "visa",
                        "success": "true",
                    }
                }
            ],
        }
        self.assertTrue(self.view._is_valid_payload_hmac(payload))

    @responses.activate
    @patch(
        'payments.views.AdyenNotificationView._is_valid_payload_hmac', return_value=True
    )
    def test_proper_request_returns_200(self, mocked_hmac_validator):
        response = self.client.post(
            self.url,
            json.dumps(self.data),
            content_type='application/json',
            **self.headers,
        )
        mocked_hmac_validator.assert_called_once_with(self.data)

    def test_get_zendesk_payload(self):
        item = self.item_data['NotificationRequestItem']

        comment = self.view._get_zendesk_payload(self.user, item)['comment']

        self.assertIn(self.user.name, comment)
        self.assertIn(item['eventCode'], comment)


class Adyen3DSTestCase(AdyenBaseTestCase):
    @patch('amuse.tasks.zendesk_create_or_update_user')
    def setUp(self, zendesk_mock):
        self.user = UserFactory()
        self.payment = PaymentTransactionFactory(
            user=self.user, status=PaymentTransaction.STATUS_NOT_SENT
        )
        self.client.force_login(user=self.user)

    @responses.activate
    def test_post_updates_payment_transaction_returns_302(self):
        url = reverse(
            'adyen_3ds',
            kwargs={
                'payment_id': self.payment.pk,
                'encrypted_user_id': TimestampSigner().sign(self.user.pk),
            },
        )
        self._add_country_check_response(self.payment.country.code)
        self._add_checkout_response('Authorised', endpoint='payments/details')

        response = self.client.post(url, {'dummy': 'data'})
        self.payment.refresh_from_db()

        token = payment_success_token_generator.make_token(
            {'transaction_id': self.payment.id}
        )
        flow = self.payment.amount == 0 and 'auth' or 'checkout'
        with patch.object(
            payment_success_token_generator, 'make_token', return_value=token
        ):
            return_url_str = (
                settings.WRB_URL
                + settings.ADYEN_3DS_WEBAPP_RETURN_PATH
                + 'true'
                + '&transactionid='
                + token
                + f'&flow={flow}'
            )

            self.assertEqual(response.status_code, status.HTTP_302_FOUND)
            self.assertEqual(self.payment.status, PaymentTransaction.STATUS_APPROVED)
            self.assertEqual(response.url, return_url_str)

    @responses.activate
    def test_get_updates_payment_transaction_returns_302(self):
        url = reverse(
            'adyen_3ds',
            kwargs={
                'payment_id': self.payment.pk,
                'encrypted_user_id': TimestampSigner().sign(self.user.pk),
            },
        )
        self._add_country_check_response(self.payment.country.code)
        self._add_checkout_response('Authorised', endpoint='payments/details')

        response = self.client.get(url, {'dummy': 'data'})
        self.payment.refresh_from_db()

        token = payment_success_token_generator.make_token(
            {'transaction_id': self.payment.id}
        )
        flow = self.payment.amount == 0 and 'auth' or 'checkout'
        with patch.object(
            payment_success_token_generator, 'make_token', return_value=token
        ):
            return_url_str = (
                settings.WRB_URL
                + settings.ADYEN_3DS_WEBAPP_RETURN_PATH
                + 'true'
                + '&transactionid='
                + token
                + f'&flow={flow}'
            )

            self.assertEqual(response.status_code, status.HTTP_302_FOUND)
            self.assertEqual(self.payment.status, PaymentTransaction.STATUS_APPROVED)
            self.assertEqual(response.url, return_url_str)

    @responses.activate
    def test_post_invalid_data_returns_404(self):
        url = reverse(
            'adyen_3ds',
            kwargs={'payment_id': self.payment.pk, 'encrypted_user_id': '2143524635'},
        )

        response = self.client.post(url, {'dummy': 'data'})
        self.payment.refresh_from_db()

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(self.payment.status, PaymentTransaction.STATUS_NOT_SENT)

    @responses.activate
    def test_approved_payment_returns_404(self):
        self.payment.status = PaymentTransaction.STATUS_APPROVED
        self.payment.save()
        url = reverse(
            'adyen_3ds',
            kwargs={
                'payment_id': self.payment.pk,
                'encrypted_user_id': TimestampSigner().sign(self.user.pk),
            },
        )

        response = self.client.post(url, {'dummy': 'data'})

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


class Adyen3DsSendSubscriptionStartedEventTestCase(AdyenBaseTestCase):
    @patch('amuse.tasks.zendesk_create_or_update_user')
    def setUp(self, zendesk_mock):
        self.user = UserFactory()
        self.payment = PaymentTransactionFactory(
            user=self.user, status=PaymentTransaction.STATUS_NOT_SENT
        )
        self.client.force_login(user=self.user)

    @patch('payments.views.subscription_new_started')
    def test_payment_not_approved_do_not_send(self, mock_send_event):
        _send_subscription_new_started_event({}, self.payment)
        self.assertEqual(0, mock_send_event.call_count)

    @patch('payments.views.subscription_new_started')
    def test_payment_amount_is_zero_do_not_send(self, mock_send_event):
        self.payment.status = PaymentTransaction.STATUS_APPROVED
        self.payment.amount = 0

        _send_subscription_new_started_event({}, self.payment)
        self.assertEqual(0, mock_send_event.call_count)

    @patch('payments.views.subscription_new_started')
    def test_subscription_is_not_active_do_not_send(self, mock_send_event):
        self.payment.status = PaymentTransaction.STATUS_APPROVED
        self.payment.subscription.status = Subscription.STATUS_CREATED

        _send_subscription_new_started_event({}, self.payment)
        self.assertEqual(0, mock_send_event.call_count)

    @patch('payments.views.logger.error')
    def test_exception_raised(self, mock_logger):
        self.payment.status = PaymentTransaction.STATUS_APPROVED
        self.payment.subscription.status = Subscription.STATUS_ACTIVE

        _send_subscription_new_started_event({}, self.payment)
        mock_logger.assert_called_once()

    @patch('payments.views.subscription_new_started')
    def test_succesful_send_event(self, mock_send_event):
        self.payment.status = PaymentTransaction.STATUS_APPROVED
        self.payment.subscription.status = Subscription.STATUS_ACTIVE

        class MockRequest:
            def __init__(self, user_agent, forwarder):
                self.META = {
                    'HTTP_USER_AGENT': user_agent,
                    'HTTP_X_FORWARDED_FOR': forwarder,
                }

        request = MockRequest('android:1.23;1', '123.123.123.123')
        _send_subscription_new_started_event(request, self.payment)

        mock_send_event.assert_called_once_with(
            self.payment.subscription,
            PlatformType.UNKNOWN,
            request.META.get('HTTP_USER_AGENT', ''),
            '123.123.123.123',
            self.payment.country.code,
        )
