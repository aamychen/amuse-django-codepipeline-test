import json
from unittest.mock import patch
from django.test import TestCase

import responses
from django.test import override_settings

from amuse.tests.helpers import (
    add_zendesk_mock_post_response,
    ZENDESK_MOCK_API_URL_TOKEN,
)

from payments.tests.factories import PaymentTransactionFactory
from subscriptions.tests.factories import SubscriptionPlanFactory
from users.tests.factories import UserFactory
from amuse.vendor.adyen.base import AdyenGetRecurringInfo


@override_settings(
    **ZENDESK_MOCK_API_URL_TOKEN,
)
class AdyenGetRecurringInfoTestCase(TestCase):
    @responses.activate
    def setUp(self):
        add_zendesk_mock_post_response()
        self.user = UserFactory()
        self.plan = SubscriptionPlanFactory(trial_days=0)
        self.payment = PaymentTransactionFactory(
            amount=50,
            plan=self.plan,
            user=self.user,
        )
        self.fetcher = AdyenGetRecurringInfo()

    @responses.activate
    def test_get_recurring_info(self):
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

        payload = self.fetcher.get_recurring_info(self.user.pk)
        self.assertEqual(len(payload['details']), 2)
        self.assertIsInstance(payload, dict)

    @patch('amuse.vendor.adyen.base.logger')
    def test_get_reccuring_info_call_failed(self, mock_logger):
        return_value = self.fetcher.get_recurring_info(self.user.pk)
        self.assertIsNone(return_value)
        mock_logger.warning.assert_called_once_with(
            f"Error while getting recurring info error=Tests must mock all HTTP requests!"
        )
