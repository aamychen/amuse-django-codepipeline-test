import json

import responses
from dateutil.relativedelta import relativedelta
from django.conf import settings
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from rest_framework import status

from amuse.tests.helpers import (
    ZENDESK_MOCK_API_URL_TOKEN,
)
from subscriptions.tests.factories import SubscriptionFactory, SubscriptionPlanFactory
from subscriptions.tests.helpers import (
    apple_notification_payload,
    apple_receipt_validation_response,
)


@override_settings(**ZENDESK_MOCK_API_URL_TOKEN)
class AppleSubscriptionBaseTestCase(TestCase):
    def _add_receipt_response(self, *args, **kwargs):
        expires_date = timezone.now() + relativedelta(months=1)
        responses.add(
            responses.POST,
            settings.APPLE_VALIDATION_URL,
            json=apple_receipt_validation_response(expires_date=expires_date, **kwargs),
            status=200,
        )


class AppleSubscriptionViewTestCase(AppleSubscriptionBaseTestCase):
    def setUp(self):
        self.plan = SubscriptionPlanFactory(
            apple_product_id='amuse_pro_monthly_renewal', trial_days=0
        )
        self.url = reverse('apple-subscriptions')

    @responses.activate
    @override_settings(APPLE_PLATFORM='production')
    def test_staging_request_to_prod_posted_to_staging_environment(self):
        payload = apple_notification_payload()
        payload['environment'] = 'Sandbox'
        responses.add(responses.POST, settings.APPLE_STAGING_WEBHOOK_URL, status=200)

        response = self.client.post(
            self.url, json.dumps(payload), content_type='application/json'
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(responses.calls), 1, responses.calls)
        self.assertEqual(
            responses.calls[0].request.url, settings.APPLE_STAGING_WEBHOOK_URL
        )
