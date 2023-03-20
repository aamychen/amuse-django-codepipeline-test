import logging
from django.http import JsonResponse
from rest_framework.decorators import api_view, throttle_classes
from amuse.vendor.twilio.sms import TwilioException, send_download_link
from amuse.throttling import RestrictedEndpointThrottle

logger = logging.getLogger(__name__)


@api_view(['GET'])
@throttle_classes([RestrictedEndpointThrottle])
def download_link(request):
    phone = request.user.phone

    if phone:
        try:
            send_download_link(phone)
            return JsonResponse({}, status=200)
        except TwilioException as te:
            logger.error(te.message)
            return JsonResponse(
                {'error': 'Our SMS service is under maintenance at the moment.'},
                status=500,
            )
    else:
        return JsonResponse(
            {'error': 'No phone number associated with this account.'}, status=404
        )
