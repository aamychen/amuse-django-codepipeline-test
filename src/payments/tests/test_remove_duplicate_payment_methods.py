from unittest.mock import patch

from django.core.management import call_command
from django.test import TestCase

from payments.models import PaymentMethod
from payments.tests.factories import PaymentMethodFactory
from subscriptions.tests.factories import SubscriptionFactory
from users.tests.factories import UserFactory


class RemoveDuplicatePaymentMethodsTestCase(TestCase):
    @patch('amuse.tasks.zendesk_create_or_update_user')
    def test_command(self, mock_zendesk):
        user = UserFactory()
        original_payment_method = PaymentMethodFactory(
            external_recurring_id='123', method='visa', summary='9000', user=user
        )
        broken_payment_method = PaymentMethodFactory(
            external_recurring_id=None, method='visa', summary='9000', user=user
        )

        subscription = SubscriptionFactory(
            payment_method=broken_payment_method, user=user
        )

        call_command('remove_duplicate_payment_methods')
        subscription.refresh_from_db()

        assert subscription.payment_method == original_payment_method
        assert PaymentMethod.objects.count() == 1
