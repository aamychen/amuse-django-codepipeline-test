from django.conf import settings
from django.urls import reverse
from rest_framework import throttling

from amuse.utils import get_ip_address
from amuse.api.base.authentication import authenticate_from_otp_cookie


class RestrictedEndpointThrottle(throttling.UserRateThrottle):
    rate = '5/min'

    def allow_request(self, request, view):
        ip_address = get_ip_address(request)
        if ip_address in settings.IP_WHITE_LIST_THROTTLE:
            return True
        return super().allow_request(request, view)


class LoginEndpointThrottle(throttling.UserRateThrottle):
    rate = '5/min'
    block_time_seconds = 15 * 60

    def allow_request(self, request, view):
        ip_address = get_ip_address(request)
        if ip_address in settings.IP_WHITE_LIST_THROTTLE:
            return True

        allowed = super().allow_request(request, view)

        cache_key = f'long_throttle_{self.key}'

        if not allowed:
            blocked_until = self.block_time_seconds + self.timer()
            self.cache.set(cache_key, blocked_until, self.block_time_seconds)

            return False

        blocked_until = self.cache.get(cache_key)

        if blocked_until:
            is_blocked = blocked_until > self.timer()

            if is_blocked:
                return False
            else:
                self.cache.delete(cache_key)

        return True

    def wait(self):
        return None


class IPBlockThrottle(throttling.BaseThrottle):
    def _is_blocked(self, view_action, ip):
        s = getattr(settings, 'IP_BLOCK_THROTTLE')
        if not s:
            return False
        return view_action in s and ip in s[view_action]

    def allow_request(self, request, view):
        return not self._is_blocked(
            f'{view.basename}-{view.action}', self.get_ident(request)
        )


class SendSmsThrottle(throttling.SimpleRateThrottle):
    rate = '2/min'

    def get_cache_key(self, request, view):
        path = request._request.path
        method = request.method
        user = request.user
        sms_code = request.data.get('sms_code', None)

        if user.is_anonymous:
            # Throttle signup SMS send
            is_signup = path == reverse('user-verify-phone') and method == 'POST'
            if is_signup and not sms_code:
                # remove last 4 characters to prevent spam enumeration
                # i.e. someone sending messages to: +1-1234-0001 to +1-1234-9999
                phone = request.data.get("phone")
                return phone[0:-4]
        else:
            # Throttle phone number update SMS send
            is_update = (
                path == reverse('user-detail', kwargs={'pk': user.pk})
                and method == 'PATCH'
            )
            if is_update and not sms_code:
                new_phone = request.data.get('phone')
                if new_phone != user.phone:
                    return new_phone

        return None


class LoginSendSmsThrottle(throttling.SimpleRateThrottle):
    rate = '2/min'

    def __init__(self, user):
        super().__init__()
        self.phone = user.phone

    def get_cache_key(self, request, view):
        if request.data.get('sms_code', None):
            return None
        return self.phone


class OtpSendSmsThrottle(throttling.SimpleRateThrottle):
    rate = '2/min'

    def get_cache_key(self, request, view):
        user = authenticate_from_otp_cookie(request=request)
        if user is None:
            return None
        return f"{user.pk}_{user.phone}"
