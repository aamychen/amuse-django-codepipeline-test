import json
from django.http import HttpResponseServerError, HttpResponseBadRequest, JsonResponse
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from rest_framework import status

from ..vendor.google import warning, info, new_eventid
from ..vendor.google.notifications import GoogleBillingNotificationProcessor
from ..vendor.google.enums import ProcessingResult


class GoogleSubscriptionView(View):
    def post(self, request):
        event_id = new_eventid()
        try:
            payload = json.loads(request.body)
            info(event_id, f'Received payload: {str(payload)}')

            result = GoogleBillingNotificationProcessor(event_id).process(payload)
            if result == ProcessingResult.SUCCESS:
                return JsonResponse(data={}, status=status.HTTP_200_OK)

            return HttpResponseBadRequest()
        except Exception as ex:
            warning(event_id, f'PANIC! Unhandled exception: "{str(ex)}"')
            return HttpResponseServerError()


google_subscription_view = csrf_exempt(GoogleSubscriptionView.as_view())
