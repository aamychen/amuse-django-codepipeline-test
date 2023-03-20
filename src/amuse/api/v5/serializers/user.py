from rest_framework import serializers
from rest_framework.exceptions import PermissionDenied, ValidationError, Throttled
from rest_framework.throttling import UserRateThrottle

from amuse.api.helpers import format_otp_message
from amuse.api.v4.serializers.user import UserSerializer as UserSerializerV4
from amuse.platform import PlatformHelper
from amuse.vendor.sinch import send_otp_sms, should_use_sinch
from amuse.vendor.twilio.sms import TwilioException, send_sms_code, validate_phone
from users.models.user import OtpDevice


class SmsUserRateThrottle(UserRateThrottle):
    rate = "5/h"


class UserSerializer(UserSerializerV4):
    facebook_access_token = serializers.CharField(
        write_only=True, required=False, default=None, allow_null=True, allow_blank=True
    )
    facebook_id = serializers.CharField(
        required=False, allow_null=True, allow_blank=True
    )
    firebase_token = serializers.CharField(
        required=False, allow_null=True, allow_blank=True
    )
    google_id = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    google_id_token = serializers.CharField(
        write_only=True, required=False, default=None, allow_null=True, allow_blank=True
    )
    profile_link = serializers.CharField(
        required=False, allow_null=True, allow_blank=True
    )
    profile_photo = serializers.CharField(
        required=False, allow_null=True, allow_blank=True
    )

    otp_enabled = serializers.BooleanField(read_only=True, default=False)
    phone_verified = serializers.BooleanField(read_only=True, default=False)
    sms_code = serializers.CharField(
        required=False, max_length=6, default=None, write_only=True
    )
    has_hyperwallet_token = serializers.BooleanField(read_only=True)
    phone = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    tier = serializers.IntegerField(read_only=True, default=0)
    is_free_trial_active = serializers.BooleanField(read_only=True, default=False)
    is_free_trial_eligible = serializers.BooleanField(default=False, read_only=True)
    is_frozen = serializers.BooleanField(read_only=True)
    is_fraud_attempted = serializers.BooleanField(read_only=True, default=False)
    impact_click_id = serializers.CharField(
        write_only=True, allow_null=True, allow_blank=True, required=False
    )
    hyperwallet_integration = serializers.CharField(read_only=True)
    payee_profile_exist = serializers.BooleanField(read_only=True)

    def validate(self, validated_data):
        user = self.context['request'].user
        is_signup = user.is_anonymous
        phone = validated_data.get('phone')
        sms_code = validated_data.pop('sms_code', None)
        is_apple_signin_user = validated_data.get('apple_signin_id')
        verify_phone = validated_data.get('verify_phone', None)

        if not is_apple_signin_user and not phone:
            raise ValidationError({'phone': ['This field is required.']})

        if is_signup and not is_apple_signin_user:
            validation_error = ValidationError({'phone': 'Phone needs to be verifed'})
            try:
                otp = OtpDevice.objects.get(user=None, phone=phone)
                if otp.is_verified:
                    phone = validate_phone(phone)
                    validated_data['phone'] = phone
                    validated_data['phone_verified'] = True
                    validated_data['otp_enabled'] = True
                    otp.delete()
                else:
                    raise validation_error
            except OtpDevice.DoesNotExist:
                raise validation_error
            except OtpDevice.MultipleObjectsReturned:
                raise PermissionDenied(
                    {'OtpDeviceError': 'Invalid number of OtpDevices'}
                )

        elif (not is_signup and user.phone != phone) or verify_phone:
            if not user.otp_enabled and not user.phone_verified:
                validated_data.pop('phone', None)
            else:
                throttle = SmsUserRateThrottle()
                if not throttle.allow_request(self.context["request"], None):
                    raise Throttled()

                phone = validate_phone(phone)

                if self._is_valid_otp(phone, sms_code, user):
                    validated_data['phone'] = phone
                    validated_data['phone_verified'] = True
                    validated_data['otp_enabled'] = True
                else:
                    raise ValidationError({'sms_code': 'Invalid code'})

        return super().validate(validated_data)

    def _is_valid_otp(self, phone, sms_code, user):
        otp = OtpDevice.objects.get_unique_otp_device(user=user)
        if otp.otp_secret and otp.is_valid_code(sms_code):
            return True
        elif not sms_code:
            sms_code = otp.update_code()

            platform = PlatformHelper.from_request(self.context['request'])
            sms_message = format_otp_message(sms_code, platform)
            if should_use_sinch(phone):
                if not send_otp_sms(phone, sms_message):
                    raise ValidationError({'sms_code': 'SMS Send Error'})
            else:
                try:
                    send_sms_code(phone, sms_message)
                except TwilioException:
                    raise ValidationError({'sms_code': 'SMS Send Error'})
        return False
