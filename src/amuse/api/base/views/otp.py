import logging
from rest_framework.response import Response
from rest_framework.decorators import permission_classes, authentication_classes
from rest_framework import permissions
from users.models.user import OtpDevice
from amuse.api.helpers import format_otp_message
from amuse.vendor.sinch import send_otp_sms, should_use_sinch
from amuse.vendor.twilio.sms import TwilioException, send_sms_code
from amuse.throttling import OtpSendSmsThrottle
from amuse.platform import PlatformHelper
from django.core.exceptions import ObjectDoesNotExist

from rest_framework.generics import GenericAPIView
from amuse.mixins import LogMixin
from amuse.api.base.authentication import authenticate_from_otp_cookie
from amuse.api.base.validators import validate_digits_input
from amuse.api.base.cookies import set_access_cookie, set_refresh_cookie
from amuse.api.v6.serializers.user import UserSerializer

logger = logging.getLogger(__name__)


def send_otp_code(phone: str, code: str, platform: str) -> bool:
    """
    Use Sinch or Twilio to deliver otp code to user via SMS
    :param phone: str phone number
    :param code: str otp code to be sent
    :param platform: str required to format sms message for Android
    :return: bool True on success False if sent operation fails
    """
    sms_message = format_otp_message(code, platform)
    if should_use_sinch(phone):
        return send_otp_sms(phone, sms_message)
    try:
        send_sms_code(phone, sms_message)
        return True
    except TwilioException as e:
        logger.error(f"Twilio send sms failed with {str(e)}")
        return False


def post_verify_phone_action(user, otp_device):
    """
    If phone is verified  update User and OtpDevice data
    :param user: User
    :param otp_device: OtpDevice
    :return:
    """
    if not otp_device.is_verified:
        otp_device.is_verified = True
        otp_device.save()
    if not user.phone_verified or not user.otp_enabled:
        user.phone_verified = True
        user.otp_enabled = True
        user.save()


@authentication_classes([])
@permission_classes([permissions.AllowAny])
class OtpTriggerView(LogMixin, GenericAPIView):
    throttle_classes = [OtpSendSmsThrottle]

    def get(self, request):
        user = authenticate_from_otp_cookie(request)
        if user is None:
            return Response({'success': False}, status=401)
        platform = PlatformHelper.from_request(self.request)
        otp = OtpDevice.objects.get_unique_otp_device(user=user)
        otp_code = otp.update_code()
        if not send_otp_code(user.phone, otp_code, platform):
            return Response({'success': False}, status=400)

        return Response({'success': True, 'otp_id': otp.pk}, status=200)


@authentication_classes([])
@permission_classes([permissions.AllowAny])
class OtpVerifyView(LogMixin, GenericAPIView):
    def post(self, request, otp_id):
        validate_digits_input(otp_id, 'otp_id')
        user = authenticate_from_otp_cookie(request)
        if user is None:
            return Response({'success': False}, status=401)
        sms_code = request.data.get('sms_code')
        try:
            otp = OtpDevice.objects.get(pk=otp_id, user=user)
        except ObjectDoesNotExist:
            return Response(
                {
                    'success': False,
                    'errors': [f"OTP device with id {otp_id} does not exist"],
                },
                status=400,
            )
        is_valid = otp.is_valid_code(sms_code)
        if is_valid:
            post_verify_phone_action(user, otp)
            response = Response(
                {
                    'success': is_valid,
                    "user": UserSerializer().to_representation(instance=user),
                },
                status=200,
            )
            set_access_cookie(response, user.pk)
            set_refresh_cookie(response, user.pk)
            return response
        return Response({'success': is_valid}, status=400)
