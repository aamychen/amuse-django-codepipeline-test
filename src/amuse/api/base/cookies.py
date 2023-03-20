from rest_framework.response import Response
from amuse.tokens import otp_token_generator
from django.conf import settings
from django.utils.module_loading import import_string


def set_otp_cookie(response: Response, user_id) -> None:
    token = otp_token_generator.make_token(user_id)
    response.set_signed_cookie(
        settings.OTP_COOKIE_NAME,
        value=token,
        secure=not settings.UNSECURE_COOKIE,
        httponly=True,
        samesite='Lax',
        max_age=int(settings.OTP_JWT_EXP_MINUTES) * 60,
    )


def set_access_cookie(response: Response, user_id) -> None:
    token_generator = import_string(settings.AUTH_TOKEN_GENERATOR_CLASS)
    response.set_signed_cookie(
        settings.ACCESS_COOKIE_NAME,
        value=token_generator.make_access_token(user_id),
        secure=not settings.UNSECURE_COOKIE,
        httponly=True,
        samesite='Lax',
        max_age=int(settings.ACCESS_TOKEN_EXP_MINUTES) * 60,
    )


def set_refresh_cookie(response: Response, user_id) -> None:
    token_generator = import_string(settings.AUTH_TOKEN_GENERATOR_CLASS)
    response.set_signed_cookie(
        settings.REFRESH_COOKIE_NAME,
        value=token_generator.make_refresh_token(user_id),
        secure=not settings.UNSECURE_COOKIE,
        httponly=True,
        samesite='Lax',
        max_age=int(settings.REFRESH_TOKEN_EXP_DAYS) * 86400,
    )
