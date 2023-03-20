from unittest.mock import patch

import responses
from django.urls import reverse
from rest_framework import status

from amuse.tests.helpers import add_zendesk_mock_post_response
from amuse.tests.test_api.base import AmuseAPITestCase, API_V5_ACCEPT_VALUE
from amuse.vendor.apple.subscriptions import (
    AppleReceiptValidationAPIClient as AppleClient,
)
from users.tests.factories import UserFactory


class AppleSubscriptionInfoTestCase(AmuseAPITestCase):
    def setUp(self):
        add_zendesk_mock_post_response()
        self.user = UserFactory()
        self.client.force_authenticate(self.user)
        self.client.credentials(HTTP_ACCEPT=API_V5_ACCEPT_VALUE)
        self.url = reverse('apple-subscription-info')

    @responses.activate
    @patch.object(AppleClient, 'validate_receipt', return_value=None)
    @patch.object(AppleClient, 'is_introductory_offer_eligible', return_value=True)
    def test_is_introductory_eligible(self, _, __):
        response = self.client.post(
            self.url, {'receipt_data': "fake-receipt-data"}, format='json'
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['is_introductory_offer_eligible'])

    @responses.activate
    @patch.object(AppleClient, 'validate_receipt', return_value=None)
    @patch.object(AppleClient, 'is_introductory_offer_eligible', return_value=False)
    def test_is_not_introductory_eligible(self, _, __):
        response = self.client.post(
            self.url, {'receipt_data': "fake-receipt-data"}, format='json'
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(response.data['is_introductory_offer_eligible'])
