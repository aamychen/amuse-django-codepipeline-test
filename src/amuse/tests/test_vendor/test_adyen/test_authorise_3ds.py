from unittest import mock

import responses

from amuse.tests.helpers import add_zendesk_mock_post_response
from amuse.tests.test_vendor.test_adyen.base import AdyenBaseTestCase
from amuse.vendor.adyen import authorise_3ds
from payments.tests.factories import PaymentTransactionFactory
from subscriptions.models import Subscription


class Authorise3dsSubscriptionTestCase(AdyenBaseTestCase):
    @responses.activate
    def setUp(self):
        add_zendesk_mock_post_response()
        self.payment = PaymentTransactionFactory()
        self.user = self.payment.user
        self.data = {'MD': '123', 'PaRes': '456'}

    @responses.activate
    def test_success(self):
        self._add_checkout_response('Authorised', endpoint='payments/details')

        response = authorise_3ds(self.data, self.payment)

        self.assertTrue(response['is_success'])
        self.assertEqual(self.payment.subscription.status, Subscription.STATUS_ACTIVE)

    @responses.activate
    def test_error(self):
        self._add_checkout_response('Error', endpoint='payments/details')

        response = authorise_3ds(self.data, self.payment)

        self.assertFalse(response['is_success'])
        self.assertEqual(self.payment.subscription.status, Subscription.STATUS_ACTIVE)

    @responses.activate
    def test_unsupported_status(self):
        self._add_checkout_response('NewUnsupported', endpoint='payments/details')

        with self.assertRaises(Exception) as context:
            self.assertFalse(authorise_3ds(self.data, self.payment)['is_success'])

        self.assertIn('unsupported result code', context.exception.message)
        self.assertEqual(self.payment.subscription.status, Subscription.STATUS_ERROR)
