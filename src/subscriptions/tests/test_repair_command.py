import json
from unittest.mock import patch, Mock
from django.db import DatabaseError
from django.test import TestCase
from django.core.management import call_command
import responses
from django.test import override_settings

from amuse.tests.helpers import (
    add_zendesk_mock_post_response,
    ZENDESK_MOCK_API_URL_TOKEN,
)

from payments.tests.factories import PaymentTransactionFactory
from subscriptions.tests.factories import SubscriptionPlanFactory
from users.tests.factories import UserFactory
from subscriptions.models import Subscription


def connection_error():
    raise Exception


@override_settings(
    **ZENDESK_MOCK_API_URL_TOKEN,
)
class RepairSubscriptionsTestCase(TestCase):
    cursor_wrapper = Mock()
    cursor_wrapper.side_effect = DatabaseError

    @responses.activate
    def setUp(self):
        add_zendesk_mock_post_response()
        self.user = UserFactory()
        self.plan = SubscriptionPlanFactory(trial_days=0)
        self.payment = PaymentTransactionFactory(
            amount=50,
            plan=self.plan,
            user=self.user,
            external_transaction_id='853606225549705G',
        )
        self.subscriptiion = self.payment.subscription
        self.subscriptiion.provider = Subscription.PROVIDER_ADYEN

    @responses.activate
    def test_fix_recurring_id(self):
        responses.add(
            responses.POST,
            "https://pal-test.adyen.com/pal/servlet/Recurring/v25/listRecurringDetails",
            json.dumps(
                {
                    'creationDate': '2020-11-24T14:45:50+01:00',
                    'details': [
                        {
                            'RecurringDetail': {
                                'additionalData': {'cardBin': '491761'},
                                'alias': 'C931323385165092',
                                'aliasType': 'Default',
                                'card': {
                                    'expiryMonth': '3',
                                    'expiryYear': '2030',
                                    'holderName': 'Checkout Shopper PlaceHolder',
                                    'number': '0000',
                                },
                                'contractTypes': ['ONECLICK', 'RECURRING'],
                                'creationDate': '2021-02-12T12:12:35+01:00',
                                'firstPspReference': '882613128349482A',
                                'name': '3335',
                                'paymentMethodVariant': 'visacredit',
                                'recurringDetailReference': '8416131283555394',
                                'variant': 'visa',
                            }
                        },
                        {
                            'RecurringDetail': {
                                'additionalData': {'cardBin': '416667'},
                                'alias': 'A763578160925052',
                                'aliasType': 'Default',
                                'card': {
                                    'expiryMonth': '3',
                                    'expiryYear': '2030',
                                    'holderName': 'jhdgf',
                                    'number': '6746',
                                },
                                'contractTypes': ['ONECLICK', 'RECURRING'],
                                'creationDate': '2021-04-19T17:02:34+02:00',
                                'firstPspReference': '853606225549705G',
                                'name': '4887',
                                'paymentMethodVariant': 'visacredit',
                                'recurringDetailReference': '8416062255506117',
                                'variant': 'visa',
                            }
                        },
                    ],
                    'lastKnownShopperEmail': self.user.email,
                    'shopperReference': self.user.pk,
                }
            ),
            status=200,
        )
        call_command(
            'repair_subscription_data',
            '--fix_payment_methods=true',
        )
        payment_method = self.payment.payment_method
        payment_method.refresh_from_db()
        self.assertEqual(payment_method.method, 'visa')
        self.assertEqual(payment_method.external_recurring_id, '8416062255506117')

    @patch('subscriptions.management.commands.repair_subscription_data.logger.warning')
    def test_fix_recurring_id_failed(self, mock_logger):
        call_command(
            'repair_subscription_data',
            '--fix_payment_methods=true',
        )
        mock_logger.assert_called_once()

    @patch('subscriptions.management.commands.repair_subscription_data.logger.warning')
    @patch("django.db.backends.utils.CursorWrapper", cursor_wrapper)
    def test_db_issue_case(self, mock_logger):
        call_command(
            'repair_subscription_data',
            '--fix_payment_methods=true',
        )
        mock_logger.assert_called_once_with(
            'DB error while fixing adyen payment method data error='
        )
