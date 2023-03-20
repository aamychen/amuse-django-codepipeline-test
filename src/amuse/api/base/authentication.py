from rest_framework.request import HttpRequest
from amuse.tokens import otp_token_generator
from django.conf import settings
from users.models import User
from django.core.exceptions import ObjectDoesNotExist
from django.utils.module_loading import import_string
from rest_framework.exceptions import AuthenticationFailed
from rest_framework.authentication import BaseAuthentication


def authenticate_from_otp_cookie(request: HttpRequest):
    raw_token = request.get_signed_cookie(settings.OTP_COOKIE_NAME, default=None)
    if raw_token is None:
        raise AuthenticationFailed({"reason": "Missing token", "code": 'missing-token'})
    user_id = otp_token_generator.get_user_id(raw_token)
    try:
        user = User.objects.get(id=user_id)
        if not user.is_active:
            raise AuthenticationFailed(
                {"reason": "User account is deactivated", "code": 'user-deactivated'}
            )
        return user
    except (ObjectDoesNotExist, TypeError):
        return None


class JWTCookieAuthentication(BaseAuthentication):
    token_generator_class = import_string(settings.AUTH_TOKEN_GENERATOR_CLASS)

    def authenticate(self, request):
        token = request.get_signed_cookie(settings.ACCESS_COOKIE_NAME, default=None)
        if token is None:
            return None
        user_id = self.token_generator_class.get_user_id(token)
        try:
            user = User.objects.get(id=user_id)
            if not user.is_active:
                raise AuthenticationFailed(
                    {
                        "reason": "User account is deactivated",
                        "code": 'user-deactivated',
                    }
                )
            return user, token
        except (ObjectDoesNotExist, TypeError):
            raise AuthenticationFailed(
                {"reason": "User account not found", "code": 'user-not-found'}
            )
