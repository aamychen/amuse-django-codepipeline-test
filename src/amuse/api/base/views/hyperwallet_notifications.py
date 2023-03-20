import json
from django.conf import settings
from django.template.response import HttpResponse
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from rest_framework import status


from amuse.utils import is_authenticated_http
from payouts.notifications.hw_notification_main_handler import (
    HyperWalletNotificationHandler,
)
from amuse.logging import logger
from amuse.mixins import LogMixin


class HyperwalletNotificationView(LogMixin, View):
    def post(self, request):
        if not is_authenticated_http(
            request,
            settings.HYPERWALLET_NOTIFICATION_USER,
            settings.HYPERWALLET_NOTIFICATION_PASSWORD,
        ):
            return HttpResponse(status=status.HTTP_401_UNAUTHORIZED)

        logger.info(f'Hyperwallet Notification webhook: {request.body}')
        data = json.loads(request.body)
        handle_status = HyperWalletNotificationHandler(
            payload=data
        ).process_notification()
        if handle_status["is_success"] is True:
            return HttpResponse(['OK'], status=status.HTTP_200_OK)
        return HttpResponse(status=status.HTTP_400_BAD_REQUEST)


hyperwallet_notification_view = csrf_exempt(HyperwalletNotificationView.as_view())
