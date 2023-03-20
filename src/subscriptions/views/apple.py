import json
import logging
from uuid import uuid4

import requests
from django.conf import settings
from django.http import HttpResponse
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from rest_framework import status
from subscriptions.vendor.apple.apple import AppleNotificationHandler

logger = logging.getLogger(__name__)


class AppleSubscriptionView(View):
    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)

        self.payload = None
        self.receipt = None
        self.subscription = None
        self.request_id = None
        self.allow_expired = False

    def post(self, request):
        self.payload = json.loads(request.body)
        self.payload.pop('password', '')
        self.request_id = str(uuid4())
        logger.info(
            f'request_id: {self.request_id} - Apple Subscription webhook: {self.payload}'
        )

        # Since Apple only allows one receipts endpoint, forward Sandbox requests
        # to Amuse staging environment.
        if (
            settings.APPLE_PLATFORM == 'production'
            and self.payload.get('environment', '') == 'Sandbox'
        ):
            logger.info('Redirecting to staging')
            requests.post(settings.APPLE_STAGING_WEBHOOK_URL, json=self.payload)

            return HttpResponse(status=status.HTTP_200_OK)

        return AppleNotificationHandler().process_notification(self.payload)


apple_subscription_view = csrf_exempt(AppleSubscriptionView.as_view())
