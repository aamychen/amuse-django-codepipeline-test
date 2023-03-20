from datetime import datetime

import responses
from dateutil.relativedelta import relativedelta

from amuse.tests.helpers import add_zendesk_mock_post_response
from amuse.tests.test_vendor.test_adyen.base import AdyenBaseTestCase
from amuse.tests.test_vendor.test_adyen.helpers import mock_payment_details
from amuse.utils import CLIENT_WEB
from amuse.vendor.adyen import authorise_payment_method
from countries.tests.factories import CountryFactory
from payments.models import PaymentTransaction, PaymentMethod
from payments.tests.factories import PaymentTransactionFactory
from subscriptions.models import Subscription, SubscriptionPlanChanges
from subscriptions.tests.factories import SubscriptionFactory, SubscriptionPlanFactory
from users.tests.factories import UserFactory


class AuthorisePaymentMethodTestCase(AdyenBaseTestCase):
    @responses.activate
    def setUp(self):
        add_zendesk_mock_post_response()
        self.user = UserFactory()
        self.plan = SubscriptionPlanFactory(trial_days=0)
        self.previous_subscription = SubscriptionFactory(
            user=self.user, status=Subscription.STATUS_ACTIVE, plan=self.plan
        )
        payment_method = PaymentMethod.objects.last()
        PaymentTransactionFactory(
            subscription=self.previous_subscription,
            user=self.user,
            payment_method=payment_method,
        )
        self.country = CountryFactory()
        self.dummy_ip = '127.0.0.1'
        self.dummy_browser_info = {'sent': 'to adyen'}

    @responses.activate
    def test_success(self):
        card_token = 'new_card_token'
        additional_data = {'recurring.recurringDetailReference': card_token}
        self._add_checkout_response('Authorised')

        response = authorise_payment_method(
            self.user,
            mock_payment_details(),
            self.country,
            CLIENT_WEB,
            ip=self.dummy_ip,
            browser_info=self.dummy_browser_info,
        )
        payment = PaymentTransaction.objects.last()
        expected_expiry_date = (
            datetime.strptime(
                self.mock_response['additionalData']['expiryDate'], '%m/%Y'
            )
            + relativedelta(months=1, days=-1)
        ).date()

        payment_method = payment.subscription.payment_method

        self.assertTrue(response['is_success'])
        self._assert_payment_and_subscription(
            payment_status=PaymentTransaction.STATUS_APPROVED,
            subscription_user_id=self.user.pk,
            subscription_status=Subscription.STATUS_ACTIVE,
            payment_transaction_type=PaymentTransaction.TYPE_AUTHORISATION,
        )
        self.assertEqual(Subscription.objects.count(), 1)
        self.assertEqual(payment_method.method, 'visa')
        self.assertEqual(payment_method.summary, '9000')
        self.assertEqual(payment_method.expiry_date, expected_expiry_date)
        self.assertNotEqual(payment_method.external_recurring_id, card_token)

    @responses.activate
    def test_success_with_plan_change(self):
        card_token = 'new_card_token'
        additional_data = {'recurring.recurringDetailReference': card_token}
        self._add_checkout_response('Authorised')

        SubscriptionPlanChanges.objects.create(
            subscription=self.previous_subscription,
            current_plan=self.previous_subscription.plan,
            new_plan=SubscriptionPlanFactory(),
            valid=True,
        )

        response = authorise_payment_method(
            self.user,
            mock_payment_details(),
            self.country,
            CLIENT_WEB,
            ip=self.dummy_ip,
            browser_info=self.dummy_browser_info,
        )
        test_sub = Subscription.objects.get(pk=self.previous_subscription.pk)
        # Assert authorise will not cause plan change on subscription
        self.assertEqual(test_sub.plan, self.plan)

    @responses.activate
    def test_successful_payment_method_update_between_different_methods(self):
        self.assertEqual(PaymentMethod.objects.count(), 1)

        self._add_checkout_response('Authorised')
        response = authorise_payment_method(
            self.user,
            mock_payment_details(),
            self.country,
            CLIENT_WEB,
            ip=self.dummy_ip,
            browser_info=self.dummy_browser_info,
        )
        self.assertTrue(response['is_success'])
        self.assertEqual(PaymentMethod.objects.count(), 2)

        responses.reset()
        self._add_checkout_paypal(
            result_code="Authorised", include_payment_method=False
        )
        response = authorise_payment_method(
            self.user,
            mock_payment_details(),
            self.country,
            CLIENT_WEB,
            ip=self.dummy_ip,
            browser_info=self.dummy_browser_info,
        )
        self.assertTrue(response['is_success'])
        self.assertEqual(PaymentMethod.objects.count(), 3)

    @responses.activate
    def test_refused(self):
        self._add_checkout_response('Refused')

        response = authorise_payment_method(
            self.user,
            mock_payment_details(),
            self.country,
            CLIENT_WEB,
            ip=self.dummy_ip,
            browser_info=self.dummy_browser_info,
        )

        self.assertFalse(response['is_success'])
        self._assert_payment_and_subscription(
            payment_status=PaymentTransaction.STATUS_DECLINED,
            subscription_user_id=self.user.pk,
            subscription_status=Subscription.STATUS_ACTIVE,
            payment_transaction_type=PaymentTransaction.TYPE_AUTHORISATION,
        )

    @responses.activate
    def test_refused_fraud_freezes_and_flags_user(self):
        self._add_checkout_response(
            'Refused', additional_data={'inferredRefusalReason': 'FRAUD'}
        )

        response = authorise_payment_method(
            self.user,
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

        response = authorise_payment_method(
            self.user,
            mock_payment_details(),
            self.country,
            CLIENT_WEB,
            ip=self.dummy_ip,
            browser_info=self.dummy_browser_info,
        )

        self.assertFalse(response['is_success'])
        self._assert_payment_and_subscription(
            payment_status=PaymentTransaction.STATUS_CANCELED,
            subscription_user_id=self.user.pk,
            subscription_status=Subscription.STATUS_ACTIVE,
            payment_transaction_type=PaymentTransaction.TYPE_AUTHORISATION,
        )

    @responses.activate
    def test_pending(self):
        self._add_checkout_response('Pending')

        response = authorise_payment_method(
            self.user,
            mock_payment_details(),
            self.country,
            CLIENT_WEB,
            ip=self.dummy_ip,
            browser_info=self.dummy_browser_info,
        )

        self.assertFalse(response['is_success'])
        payment = PaymentTransaction.objects.last()
        # pending payments have no external transaction ID
        self.assertEqual(payment.external_transaction_id, '')
        self.assertEqual(payment.subscription.plan_id, self.plan.pk)
        self.assertEqual(payment.status, PaymentTransaction.STATUS_PENDING)
        self.assertEqual(payment.subscription.user_id, self.user.pk)
        self.assertEqual(payment.subscription.status, Subscription.STATUS_ACTIVE)
        self.assertEqual(payment.vat_percentage, payment.country.vat_percentage)

    @responses.activate
    def test_pending_with_action(self):
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

    @responses.activate
    def test_error(self):
        self._add_checkout_response('Error')

        response = authorise_payment_method(
            self.user,
            mock_payment_details(),
            self.country,
            CLIENT_WEB,
            ip=self.dummy_ip,
            browser_info=self.dummy_browser_info,
        )

        self.assertFalse(response['is_success'])
        self._assert_payment_and_subscription(
            payment_status=PaymentTransaction.STATUS_ERROR,
            subscription_user_id=self.user.pk,
            subscription_status=Subscription.STATUS_ACTIVE,
            payment_transaction_type=PaymentTransaction.TYPE_AUTHORISATION,
        )

    @responses.activate
    def test_redirect(self):
        self._add_checkout_redirect()

        response = authorise_payment_method(
            self.user,
            mock_payment_details(),
            self.country,
            CLIENT_WEB,
            ip=self.dummy_ip,
            browser_info=self.dummy_browser_info,
        )
        payment = PaymentTransaction.objects.last()

        self.assertFalse(response['is_success'])
        self.assertIn('action', response)
        self.assertEqual(Subscription.objects.count(), 1)
        self.assertEqual(payment.subscription.status, Subscription.STATUS_ACTIVE)
        self.assertEqual(payment.type, PaymentTransaction.TYPE_AUTHORISATION)

    @responses.activate
    def test_unsupported_status(self):
        self._add_checkout_response('NewUnsupported')

        with self.assertRaises(Exception) as context:
            self.assertFalse(
                authorise_payment_method(
                    self.user,
                    mock_payment_details(),
                    self.country,
                    CLIENT_WEB,
                    self.dummy_ip,
                    self.dummy_browser_info,
                )['is_success']
            )

        self.assertIn('unsupported result code', context.exception.message)
        self._assert_payment_and_subscription(
            payment_status=PaymentTransaction.STATUS_ERROR,
            subscription_user_id=self.user.pk,
            subscription_status=Subscription.STATUS_ERROR,
            payment_transaction_type=PaymentTransaction.TYPE_AUTHORISATION,
        )

    @responses.activate
    def test_invalid_payment_details(self):
        external_payment_id = 'blahonga'
        self._add_error_response(external_payment_id)

        response = authorise_payment_method(
            self.user,
            {'invalid': 'data'},
            self.country,
            CLIENT_WEB,
            ip=self.dummy_ip,
            browser_info=self.dummy_browser_info,
        )
        payment = PaymentTransaction.objects.last()

        self.assertFalse(response['is_success'])
        self.assertEqual(payment.external_transaction_id, external_payment_id)
        self.assertEqual(payment.subscription.plan_id, self.plan.pk)
        self.assertEqual(payment.status, PaymentTransaction.STATUS_ERROR)
        self.assertEqual(payment.subscription.user_id, self.user.pk)
        self.assertEqual(payment.subscription.status, Subscription.STATUS_ERROR)
        self.assertEqual(payment.type, PaymentTransaction.TYPE_AUTHORISATION)

    @responses.activate
    def test_3ds_mandated_no_additional_actions_required_completes_transaction(self):
        self._add_checkout_response(
            'Refused', additional_data={'inferredRefusalReason': '3D Secure Mandated'}
        )
        self._add_checkout_response('Authorised')

        response = authorise_payment_method(
            self.user,
            mock_payment_details(),
            self.country,
            CLIENT_WEB,
            ip=self.dummy_ip,
            browser_info=self.dummy_browser_info,
        )

        self.assertTrue(response['is_success'])
        self.assertEqual(Subscription.objects.count(), 1)

    @responses.activate
    def test_3ds_mandated_redirect_action_required(self):
        self._add_checkout_response(
            'Refused', additional_data={'inferredRefusalReason': '3D Secure Mandated'}
        )
        self._add_checkout_redirect()

        response = authorise_payment_method(
            self.user,
            mock_payment_details(),
            self.country,
            CLIENT_WEB,
            ip=self.dummy_ip,
            browser_info=self.dummy_browser_info,
        )
        payment = PaymentTransaction.objects.last()

        self.assertFalse(response['is_success'])
        self.assertIn('action', response)
        self.assertEqual(Subscription.objects.count(), 1)
        self.assertEqual(payment.subscription.status, Subscription.STATUS_ACTIVE)
        self.assertEqual(payment.type, PaymentTransaction.TYPE_AUTHORISATION)
