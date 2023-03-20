import json
from datetime import datetime
from decimal import Decimal
from unittest import mock

import responses
from dateutil.relativedelta import relativedelta
from django.utils import timezone

from amuse.tests.helpers import add_zendesk_mock_post_response
from amuse.tests.test_vendor.test_adyen.base import AdyenBaseTestCase
from amuse.tests.test_vendor.test_adyen.helpers import (
    mock_payment_challenge_shopper,
    mock_payment_details,
    mock_payment_identify_shopper,
)
from amuse.utils import CLIENT_WEB
from amuse.vendor.adyen import create_subscription
from countries.tests.factories import CountryFactory
from payments.models import PaymentTransaction
from subscriptions.models import Subscription
from subscriptions.tests.factories import SubscriptionPlanFactory
from users.tests.factories import UserFactory


class CreateSubscriptionTestCase(AdyenBaseTestCase):
    @responses.activate
    def setUp(self):
        add_zendesk_mock_post_response()
        self.user = UserFactory()
        self.plan = SubscriptionPlanFactory(trial_days=0)
        self.country = CountryFactory()

    @responses.activate
    @mock.patch('amuse.vendor.adyen.base.calculate_vat')
    def test_success(self, mock_vat):
        mock_vat.return_value = (Decimal('12.34'), Decimal('321.11'))
        self._add_checkout_response('Authorised')

        response = create_subscription(
            self.user,
            self.plan,
            mock_payment_details(),
            self.country,
            CLIENT_WEB,
            ip=None,
            browser_info=None,
        )
        payment = PaymentTransaction.objects.last()
        payment_method = payment.subscription.payment_method
        expected_expiry_date = (
            datetime.strptime(
                self.mock_response['additionalData']['expiryDate'], "%m/%Y"
            )
            + relativedelta(months=1, days=-1)
        ).date()

        self.assertTrue(response['is_success'])
        self.assertEqual(payment.platform, PaymentTransaction.PLATFORM_WEB)
        self.assertEqual(payment.category, PaymentTransaction.CATEGORY_INITIAL)
        self.assertEqual(payment.vat_amount_sek, Decimal('321.11'))
        self.assertEqual(payment.vat_amount, Decimal('12.34'))
        self._assert_payment_and_subscription(
            payment_status=PaymentTransaction.STATUS_APPROVED,
            subscription_user_id=self.user.pk,
            subscription_status=Subscription.STATUS_ACTIVE,
        )
        self.assertEqual(payment_method.method, 'visa')
        self.assertEqual(payment_method.summary, '9000')
        self.assertEqual(payment_method.expiry_date, expected_expiry_date)
        self.assertEqual(
            self.user.current_subscription().paid_until,
            timezone.now().date() + relativedelta(months=self.plan.period),
        )

        adyen_request_payload = json.loads(responses.calls[0].request.body)
        self.assertEqual(
            adyen_request_payload['shopperEmail'],
            self.user.email,
            adyen_request_payload,
        )

    @responses.activate
    def test_refused(self):
        self._add_checkout_response('Refused')

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
        self._assert_payment_and_subscription(
            payment_status=PaymentTransaction.STATUS_DECLINED,
            subscription_user_id=self.user.pk,
            subscription_status=Subscription.STATUS_ERROR,
        )

    @responses.activate
    def test_refused_fraud_freezes_and_flags_user(self):
        self._add_checkout_response(
            'Refused', additional_data={'inferredRefusalReason': 'FRAUD'}
        )

        response = create_subscription(
            self.user,
            self.plan,
            mock_payment_details(),
            self.country,
            CLIENT_WEB,
            ip=None,
            browser_info=None,
        )
        payment = PaymentTransaction.objects.last()
        self.user.refresh_from_db()

        self.assertFalse(response['is_success'])
        self.assertEqual(payment.subscription.status, Subscription.STATUS_ERROR)
        self.assertTrue(self.user.usermetadata.is_fraud_attempted)

    @responses.activate
    def test_canceled(self):
        self._add_checkout_response('Cancelled')

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
        self._assert_payment_and_subscription(
            payment_status=PaymentTransaction.STATUS_CANCELED,
            subscription_user_id=self.user.pk,
            subscription_status=Subscription.STATUS_ERROR,
        )

    @responses.activate
    def test_pending(self):
        self._add_checkout_response('Pending')

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
        payment = PaymentTransaction.objects.last()
        # pending payments have no external transaction ID
        self.assertEqual(payment.external_transaction_id, '')
        self.assertEqual(payment.subscription.plan_id, self.plan.pk)
        self.assertEqual(payment.status, PaymentTransaction.STATUS_PENDING)
        self.assertEqual(payment.subscription.user_id, self.user.pk)
        self.assertEqual(payment.subscription.status, Subscription.STATUS_ERROR)
        self.assertEqual(payment.vat_percentage, payment.country.vat_percentage)

    @responses.activate
    def test_pending_with_action(self):
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

    @responses.activate
    def test_error(self):
        self._add_checkout_response('Error')

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
        self._assert_payment_and_subscription(
            payment_status=PaymentTransaction.STATUS_ERROR,
            subscription_user_id=self.user.pk,
            subscription_status=Subscription.STATUS_ERROR,
        )

    @responses.activate
    def test_redirect(self):
        self._add_checkout_redirect()

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
        self.assertIn('action', response)

    @responses.activate
    def test_unsupported_status(self):
        self._add_checkout_response('NewUnsupported')

        with self.assertRaises(Exception) as context:
            self.assertFalse(
                create_subscription(
                    self.user,
                    self.plan,
                    mock_payment_details(),
                    self.country,
                    CLIENT_WEB,
                    None,
                    None,
                )['is_success']
            )

        self.assertIn('unsupported result code', context.exception.message)
        self._assert_payment_and_subscription(
            payment_status=PaymentTransaction.STATUS_ERROR,
            subscription_user_id=self.user.pk,
            subscription_status=Subscription.STATUS_ERROR,
        )

    @responses.activate
    def test_invalid_payment_details(self):
        external_payment_id = 'blahonga'
        self._add_error_response(external_payment_id)

        response = create_subscription(
            self.user,
            self.plan,
            {'invalid': 'data'},
            self.country,
            CLIENT_WEB,
            ip=None,
            browser_info=None,
        )
        payment = PaymentTransaction.objects.last()

        self.assertFalse(response['is_success'])
        self.assertEqual(payment.external_transaction_id, external_payment_id)
        self.assertEqual(payment.subscription.plan_id, self.plan.pk)
        self.assertEqual(payment.status, PaymentTransaction.STATUS_ERROR)
        self.assertEqual(
            payment.subscription.valid_until, payment.subscription.paid_until
        )
        self.assertEqual(payment.subscription.user_id, self.user.pk)
        self.assertEqual(payment.subscription.status, Subscription.STATUS_ERROR)

    @responses.activate
    def test_3ds_mandated_no_additional_actions_required_completes_transaction(self):
        self._add_checkout_response(
            'Refused', additional_data={'inferredRefusalReason': '3D Secure Mandated'}
        )
        self._add_checkout_response('Authorised')

        response = create_subscription(
            self.user,
            self.plan,
            mock_payment_details(),
            self.country,
            CLIENT_WEB,
            ip=None,
            browser_info=None,
        )
        payment = PaymentTransaction.objects.last()

        self.assertTrue(response['is_success'])
        self.assertEqual(payment.subscription.status, Subscription.STATUS_ACTIVE)

    @responses.activate
    def test_3ds_mandated_redirect_action_required(self):
        self._add_checkout_response(
            'Refused', additional_data={'inferredRefusalReason': '3D Secure Mandated'}
        )
        self._add_checkout_redirect()

        response = create_subscription(
            self.user,
            self.plan,
            mock_payment_details(),
            self.country,
            CLIENT_WEB,
            ip=None,
            browser_info=None,
        )
        payment = PaymentTransaction.objects.last()

        self.assertFalse(response['is_success'])
        self.assertIn('action', response)
        self.assertEqual(response['transaction_id'], payment.pk)
        self.assertEqual(payment.subscription.status, Subscription.STATUS_CREATED)

    @responses.activate
    def test_3ds_identify_shopper(self):
        adyen_response = mock_payment_identify_shopper()
        responses.add(
            responses.POST,
            "https://checkout-test.adyen.com/v49/payments",
            json.dumps(adyen_response),
            status=200,
        )

        response = create_subscription(
            self.user,
            self.plan,
            mock_payment_details(),
            self.country,
            CLIENT_WEB,
            ip=None,
            browser_info=None,
        )
        payment = PaymentTransaction.objects.last()

        self.assertFalse(response['is_success'])
        self.assertEqual(response['action'], adyen_response['action'])
        self.assertEqual(
            payment.customer_payment_payload, adyen_response['paymentData']
        )
        self.assertEqual(payment.subscription.status, Subscription.STATUS_CREATED)
        self.assertEqual(payment.status, PaymentTransaction.STATUS_NOT_SENT)

    @responses.activate
    def test_3ds_challenge_shopper(self):
        adyen_response = mock_payment_challenge_shopper()
        responses.add(
            responses.POST,
            "https://checkout-test.adyen.com/v49/payments",
            json.dumps(adyen_response),
            status=200,
        )

        response = create_subscription(
            self.user,
            self.plan,
            mock_payment_details(),
            self.country,
            CLIENT_WEB,
            ip=None,
            browser_info=None,
        )
        payment = PaymentTransaction.objects.last()

        self.assertFalse(response['is_success'])
        self.assertEqual(response['action'], adyen_response['action'])
        self.assertEqual(
            payment.customer_payment_payload, adyen_response['paymentData']
        )
        self.assertEqual(payment.subscription.status, Subscription.STATUS_CREATED)
        self.assertEqual(payment.status, PaymentTransaction.STATUS_NOT_SENT)
