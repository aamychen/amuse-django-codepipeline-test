import binascii
import logging
import os
from typing import Union, Type, Literal

import requests
from django.contrib.auth import authenticate
from django.core import exceptions
from rest_framework import mixins, permissions, status, viewsets
from rest_framework.authtoken.models import Token
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError, PermissionDenied
from rest_framework.response import Response
from waffle import flag_is_active, switch_is_active

from amuse import mixins as logmixins
from amuse.analytics import login_succeeded, user_requested_account_delete
from amuse.api.base.cookies import set_otp_cookie
from amuse.api.base.validators import validate_social_login_request_version
from amuse.api.base.views.exceptions import WrongAPIversionError
from amuse.api.helpers import format_otp_message
from amuse.api.v2 import serializers as serializers_v2
from amuse.api.v4.serializers.user import UserSerializer as UserSerializerV4
from amuse.api.v5.serializers.user import UserSerializer as UserSerializerV5
from amuse.api.v6.serializers import (
    FacebookLoginSerializer,
    AppleLoginSerializer,
    GoogleLoginSerializer,
)
from amuse.api.v6.serializers.user import UserSerializer as UserSerializerV6
from amuse.permissions import ReCaptchaPermission
from amuse.platform import PlatformHelper
from amuse.services.usermanagement import UserLoginService
from amuse.tasks import (
    refresh_spotify_artist_images,
    send_email_verification_email,
    send_password_reset_email,
)
from amuse.throttling import (
    LoginEndpointThrottle,
    LoginSendSmsThrottle,
    SendSmsThrottle,
)
from amuse.utils import (
    CLIENT_ANDROID,
    CLIENT_IOS,
    CLIENT_OPTIONS,
    generate_password_reset_url,
    parse_client_data,
    parse_client_version,
    is_verify_phone_mismatch_country_blocked,
)
from amuse.vendor.apple_signin import login as apple_authenticate
from amuse.vendor.customerio.events import default as customerio
from amuse.vendor.sinch import send_otp_sms, should_use_sinch
from amuse.vendor.twilio.sms import TwilioException, send_sms_code, validate_phone
from app.forms import PasswordResetForm
from countries.models import Country
from releases.models import Release
from slayer import clientwrapper as slayer
from subscriptions.models import SubscriptionPlan
from users.models import ArtistV2, User
from users.models.user import OtpDevice, UserMetadata

logger = logging.getLogger(__name__)


class SuspiciousWithdrawal(exceptions.SuspiciousOperation):
    pass


class UserViewSet(
    logmixins.LogMixin,
    mixins.CreateModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet,
):
    queryset = User.objects.all()
    permission_classes = (permissions.AllowAny,)

    def get_permissions(self):
        if self.action == 'create' and self.request.version == '6':
            self.permission_classes = self.permission_classes + (ReCaptchaPermission,)

        return [permission() for permission in self.permission_classes]

    def get_queryset(self):
        return User.objects.filter(pk=self.request.user.id)

    def get_serializer_class(self):
        if self.request.version == '6' and switch_is_active('auth:v6:enabled'):
            return UserSerializerV6
        if self.request.version == '5':
            return UserSerializerV5
        elif self.request.version == '4':
            return UserSerializerV4
        elif self.request.version in ['1', '2', '3']:
            raise WrongAPIversionError

        return UserSerializerV5

    def get_serializer_context(self):
        context = super(UserViewSet, self).get_serializer_context()
        context.update({"request": self.request})
        return context

    def get_social_login_serializer_class(self):
        return UserSerializerV5

    def get_throttles(self):
        if self.request.version == '5':
            return (SendSmsThrottle(),)
        return []

    def _response(self, obj=None):
        return Response([obj] if obj else [])

    @action(
        methods=['get', 'post'],
        detail=False,
        permission_classes=(permissions.AllowAny,),
    )
    def facebook(self, request):
        validate_social_login_request_version(request)

        if request.version == '7':
            return self._social_login_v7(request, 'facebook', FacebookLoginSerializer)

        # GET is legacy for v1
        if request.method == 'GET':
            params = request.query_params
        else:
            params = request.data
        facebook_id = params.get('facebook_id')
        facebook_access_token = params.get('facebook_access_token')

        if not facebook_id or not facebook_access_token:
            return self._response()

        r = requests.get(
            'https://graph.facebook.com/v8.0/me',
            params={
                'access_token': facebook_access_token,
                'fields': 'first_name,last_name',
            },
        )
        try:
            r.raise_for_status()
        except requests.exceptions.HTTPError:
            return self._response()
        u = r.json()
        if not u or u.get('id') != facebook_id:
            return self._response()
        user = None
        try:
            user = User.objects.active.get(facebook_id=facebook_id)
        except User.DoesNotExist:
            pass
        if not user:
            return self._response()
        if user.is_delete_requested:
            return Response(
                {'email': 'User is deleted'}, status=status.HTTP_400_BAD_REQUEST
            )

        if not user.first_name or not user.last_name:
            user.first_name = u.get('first_name')
            user.last_name = u.get('last_name')
            user.save()

        if user.has_artist_with_spotify_id():
            refresh_spotify_artist_images.delay(user.id)

        return self._response(self.get_social_login_serializer_class()(user).data)

    @action(
        methods=['get', 'post'],
        detail=False,
        permission_classes=(permissions.AllowAny,),
    )
    def google(self, request):
        validate_social_login_request_version(request)

        if request.version == '7':
            return self._social_login_v7(request, 'google', GoogleLoginSerializer)

        # GET is legacy for v1
        if request.method == 'GET':
            params = request.query_params
        else:
            params = request.data
        google_id = params.get('google_id')
        google_id_token = params.get('google_id_token')

        if not google_id or not google_id_token:
            return self._response()

        r = requests.get(
            'https://www.googleapis.com/oauth2/v3/tokeninfo',
            params={'id_token': google_id_token},
        )
        try:
            r.raise_for_status()
        except requests.exceptions.HTTPError:
            return self._response()
        u = r.json()
        if not u or u.get('sub') != google_id:
            return self._response()
        user = None
        try:
            user = User.objects.active.get(google_id=google_id)
        except User.DoesNotExist:
            pass
        if not user:
            return self._response()
        if user.is_delete_requested:
            return Response(
                {'email': 'User is deleted'}, status=status.HTTP_400_BAD_REQUEST
            )

        if not user.first_name or not user.last_name:
            user.first_name = u.get('given_name')
            user.last_name = u.get('family_name')
            user.save()

        if user.has_artist_with_spotify_id():
            refresh_spotify_artist_images.delay(user.id)

        return self._response(self.get_social_login_serializer_class()(user).data)

    @action(methods=['post'], detail=False, permission_classes=(permissions.AllowAny,))
    def apple(self, request):
        validate_social_login_request_version(request)

        if request.version == '7':
            return self._social_login_v7(request, 'apple', AppleLoginSerializer)

        access_token = request.data.get('access_token')
        apple_signin_id = request.data.get('apple_signin_id')

        if not access_token:
            raise ValidationError({'access_token': 'Missing value'})

        if not apple_signin_id:
            raise ValidationError({'apple_signin_id': 'Missing value'})

        platform = PlatformHelper.from_request(request)

        authenticated = apple_authenticate(
            platform=platform,
            access_token=access_token,
            apple_signin_id=apple_signin_id,
        )

        if not authenticated:
            return Response(
                {'error': 'unauthorized access'},
                content_type="application/json",
                status=status.HTTP_401_UNAUTHORIZED,
            )

        user = User.objects.active.filter(apple_signin_id=apple_signin_id).first()
        if not user:
            return self._response()
        if user.is_delete_requested:
            return Response(
                {'email': 'User is deleted'}, status=status.HTTP_400_BAD_REQUEST
            )

        if user and user.has_artist_with_spotify_id():
            refresh_spotify_artist_images.delay(user.id)

        return self._response(self.get_social_login_serializer_class()(user).data)

    @action(
        methods=['get', 'post'],
        detail=False,
        permission_classes=(permissions.AllowAny,),
    )
    def email(self, request):
        throttler = LoginEndpointThrottle()

        allow_request = throttler.allow_request(request, None)

        if not allow_request:
            cache_key = throttler.get_cache_key(request, None)
            ident = cache_key.replace('throttle_', '')
            logger.info('Blocked login request from ident [%s]', ident)
            return Response(status=status.HTTP_429_TOO_MANY_REQUESTS)
        if request.version == '1':
            raise WrongAPIversionError
        params = request.data

        email = params.get('email')
        password = params.get('password')
        if self.request.version == '5':
            empty_response = Response(
                {'email': 'Invalid username or password'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        else:
            empty_response = self._response()
        if not email or not password:
            return empty_response
        user = authenticate(username=email, password=password)
        if not user:
            return empty_response
        if user.is_delete_requested:
            return Response(
                {'email': 'User is deleted'}, status=status.HTTP_400_BAD_REQUEST
            )

        # Only v5 supports 2FA
        is_2fa_enabled = self._is_2fa_enabled(user)
        if self.request.version == '5':
            if is_2fa_enabled:
                sms_throttle = LoginSendSmsThrottle(user)
                if not sms_throttle.allow_request(request, self):
                    return Response(status=status.HTTP_429_TOO_MANY_REQUESTS)

                if not self._is_2fa_authenticated(
                    user, params, PlatformHelper.from_request(request)
                ):
                    return Response(
                        {'phone': user.masked_phone()},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
        elif is_2fa_enabled:
            return empty_response

        if user.has_artist_with_spotify_id():
            refresh_spotify_artist_images.delay(user.id)

        self._send_login_succeeded(request, user)

        return self._response(self.get_serializer_class()(user).data)

    @action(methods=['post'], detail=False, permission_classes=(permissions.AllowAny,))
    def password_reset(self, request):
        form = PasswordResetForm(request.data)
        if form.is_valid():
            for user in form.get_users(form.cleaned_data['email']):
                if not user.has_usable_password():
                    user.set_unusable_password()
                    user.save()
                send_password_reset_email.delay(user)
        return self._response(None)

    @action(
        methods=['post'],
        detail=False,
        permission_classes=(permissions.IsAuthenticated,),
    )
    def send_verification_email(self, request):
        send_email_verification_email.delay(self.request.user)
        return self._response(None)

    @action(
        methods=['put', 'post'],
        detail=True,
        permission_classes=(permissions.IsAuthenticated,),
        url_path='firebase-token',
        url_name='firebase-token',
    )
    def set_firebase_token(self, request, pk=None):
        user = self.request.user
        if not user or user.id != int(pk):
            raise exceptions.PermissionDenied
        firebase_token = self.request.data.get('firebase_token', None)
        if firebase_token and not len(firebase_token):
            firebase_token = None
        user.firebase_token = firebase_token
        user.save()

        client, version = parse_client_version(request.META.get("HTTP_USER_AGENT", ""))
        if firebase_token and client in (CLIENT_ANDROID, CLIENT_IOS):
            platform = "ios" if client == CLIENT_IOS else "android"
            customerio().user_updated_firebase_token(user, platform, firebase_token)

        return Response(status=status.HTTP_200_OK)

    @property
    def is_slayer_eligible(self):
        user = self.get_object()
        return user.category in (User.CATEGORY_QUALIFIED, User.CATEGORY_PRIORITY)

    @action(
        methods=['get'],
        detail=True,
        url_path='user-daily-stats',
        url_name='user-daily-stats',
        permission_classes=(permissions.IsAuthenticated,),
    )
    def user_daily_stats(self, request, pk):
        if request.version == '2':
            if self.is_slayer_eligible:
                return Response(
                    serializers_v2.UserDailyStatsSerializer(
                        slayer.legacy_user_daily_stats(self.get_object().pk) or [],
                        many=True,
                    ).data
                )
            # Added empty array as response since stats models are removed (CORE-886)
            return Response(serializers_v2.UserDailyStatsSerializer([], many=True).data)
        return Response(status=status.HTTP_501_NOT_IMPLEMENTED)

    @action(
        methods=['get'],
        detail=True,
        url_path='song-daily-stats',
        url_name='song-daily-stats',
        permission_classes=[permissions.IsAuthenticated],
    )
    def song_daily_stats(self, request, pk):
        if request.version == '2':
            if self.is_slayer_eligible:
                return Response(
                    serializers_v2.SongDailyStatsSerializer(
                        slayer.legacy_song_daily_stats(self.get_object().pk) or [],
                        many=True,
                    ).data
                )
            # As part of the old "stats" app cleanup, reference to stats model
            # is removed and set empty array instead as response (CORE-886)
            return Response(serializers_v2.SongDailyStatsSerializer([], many=True).data)
        return Response(status=status.HTTP_501_NOT_IMPLEMENTED)

    @action(
        methods=["get"],
        detail=True,
        url_path="summary",
        url_name="summary",
        permission_classes=[permissions.IsAuthenticated],
    )
    def summary(self, request, pk):
        return Response(
            slayer.summary(self.get_object().pk) or "{}",
            content_type='application/json',
        )

    @action(
        detail=False,
        url_path='main-artist-profile',
        methods=['post'],
        permission_classes=(permissions.IsAuthenticated,),
    )
    def main_artist_profile(self, request):
        # validate version
        if self.request.version != '4':
            return Response(status=status.HTTP_501_NOT_IMPLEMENTED)

        # is main_artist_profile set already?
        if request.user.userartistrole_set.filter(main_artist_profile=True).exists():
            raise ValidationError('Main Artist Profile set already')

        # validate user
        if self.request.user.tier == SubscriptionPlan.TIER_PRO:
            raise ValidationError('PRO User cannot set Main Artist Profile')

        # validate artist_id
        artist_id = request.data.get('artist_id')
        if not artist_id or not ArtistV2.objects.filter(id=artist_id).exists():
            raise ValidationError('Unknown Artist ID')

        if not request.user.userartistrole_set.filter(artist_id=artist_id).exists():
            raise ValidationError('Artist not in User team')

        # set main_artist_profile
        request.user.userartistrole_set.filter(artist_id=artist_id).update(
            main_artist_profile=True
        )

        return Response(status=status.HTTP_200_OK)

    @action(url_path='verify-phone', methods=['post'], detail=False)
    def verify_phone(self, request):
        if switch_is_active(
            "verify-phone-block-mismatch-countries:enabled"
        ) and is_verify_phone_mismatch_country_blocked(request):
            return Response(status=status.HTTP_400_BAD_REQUEST)

        sms_throttle = SendSmsThrottle()
        if not sms_throttle.allow_request(request, self):
            return Response(status=status.HTTP_429_TOO_MANY_REQUESTS)

        sms_code = request.data.get('sms_code')
        phone = validate_phone(request.data.get('phone'))

        otp = OtpDevice.objects.get_unique_otp_device(user=None, phone=phone)
        if sms_code:
            if otp.is_valid_code(sms_code) or otp.is_verified:
                otp.is_verified = True
                otp.save()
                return Response(status=status.HTTP_200_OK)
            else:
                raise ValidationError({'sms_code': 'Invalid code'})
        else:
            code = otp.update_code()
            self._send_sms_code(phone, code, PlatformHelper.from_request(request))
            raise ValidationError({'ErroMcErrorFace': 'Computer says no'})
        return Response(status=status.HTTP_200_OK)

    @action(
        methods=['delete'],
        url_path='delete',
        detail=False,
        permission_classes=[permissions.IsAuthenticated],
    )
    def account_delete_requested(self, request):
        user = self.request.user

        # Prevent users suspected of fraud/scam behaviour from being GDPR deleted
        FRAUD_FLAG_REASONS = [
            UserMetadata.FLAGGED_REASON_STREAMFARMER,
            UserMetadata.FLAGGED_REASON_SCAM,
            UserMetadata.FLAGGED_REASON_SAMPLES,
            UserMetadata.FLAGGED_REASON_INFRINGEMENTS,
            UserMetadata.FLAGGED_REASON_INFRINGEMENTS_CLAIMS,
        ]
        if (
            user.category == User.CATEGORY_FLAGGED
            and hasattr(user, "usermetadata")
            and user.usermetadata.flagged_reason in FRAUD_FLAG_REASONS
        ):
            raise PermissionDenied(
                "Your account cannot be deleted in line with our Privacy Policy. Please contact Support if you think this is incorrect."
            )

        # Prevent users with FFWD deals or licensed catalog from being GDPR deleted
        if user.has_locked_splits() or user.category == User.CATEGORY_PRIORITY:
            raise PermissionDenied(
                "Your account cannot be deleted as your releases are in a FFWD/licensed deal. Please contact Support if you think this is incorrect."
            )

        # Prevent users with live releases from being GDPR deleted
        if Release.objects.filter(
            user=user, status__in=[Release.STATUS_DELIVERED, Release.STATUS_RELEASED]
        ).exists():
            raise PermissionDenied(
                "Please take down all of your releases before deleting your account. You can remove your releases in the ‘Music’ tab."
            )

        user.flag_for_delete()
        data = {
            "user_email": user.email,
            "user_first_name": user.first_name,
            "user_last_name": user.last_name,
            "delete_requested_at": user.usermetadata.delete_requested_at,
        }
        user_requested_account_delete(user.id, data)

        # Rotate token
        Token.objects.filter(user_id=user.id).update(
            key=binascii.hexlify(os.urandom(20)).decode()
        )

        # Update any pending releases to not approved
        Release.objects.filter(
            user=user,
            status__in=[
                Release.STATUS_SUBMITTED,
                Release.STATUS_PENDING,
                Release.STATUS_APPROVED,
            ],
        ).update(status=Release.STATUS_NOT_APPROVED)

        return Response(status=status.HTTP_204_NO_CONTENT)

    def _is_2fa_authenticated(self, user, params, platform):
        sms_code = params.get('sms_code')
        otp = OtpDevice.objects.get_unique_otp_device(user=user)
        if otp.is_valid_code(sms_code):
            return True
        elif sms_code:
            raise ValidationError({'sms_code': 'Invalid code'})
        else:
            code = otp.update_code()
            self._send_sms_code(user.phone, code, platform)
            return False

    def _is_2fa_enabled(self, user):
        """2FA can be enabled/disabled for Android/iOS/web through the Waffle
        flags 2FA-android, 2FA-ios, 2FA-web. There is also 2FA-other which is
        for clients with non-conforming user agent (e.g. DDOS, web crawler).
        """
        is_2fa_user = user.phone_verified and user.otp_enabled
        client = parse_client_version(self.request.META.get('HTTP_USER_AGENT') or '')[0]
        client_name = CLIENT_OPTIONS.get(client)

        return is_2fa_user and flag_is_active(self.request, f'2FA-{client_name}')

    def _send_sms_code(self, phone, code, platform):
        sms_message = format_otp_message(code, platform)
        if should_use_sinch(phone):
            if not send_otp_sms(phone, sms_message):
                raise ValidationError({'sms_code': 'SMS Send Error'})
        else:
            try:
                send_sms_code(phone, sms_message)
            except TwilioException:
                raise ValidationError({'sms_code': 'SMS Send Error'})

    def _send_login_succeeded(self, request, user):
        client_data = parse_client_data(request)
        if client_data['country']:
            country = Country.objects.filter(code=client_data['country']).first()
            client_data['country'] = country.name if country else client_data['country']

        client_data['url'] = generate_password_reset_url(user)
        login_succeeded(user, client_data)

    def _social_login_v7(
        self,
        request,
        kind: Literal['google', 'facebook', 'apple'],
        serializer_class: Type[
            Union[FacebookLoginSerializer, GoogleLoginSerializer, AppleLoginSerializer]
        ],
    ):
        serializer = serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)
        return UserLoginService().social_login(request, kind, serializer.validated_data)

    def create(self, request):
        if self.request.version == '5':
            if not request.user.is_anonymous:
                return Response(status=status.HTTP_404_NOT_FOUND)

        if self.request.version == '6':
            serializer = self.get_serializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            user = serializer.save()
            headers = self.get_success_headers(serializer.data)
            response = Response(
                serializer.data, status=status.HTTP_201_CREATED, headers=headers
            )
            set_otp_cookie(response, user.pk)
            return response
        return super().create(request)
