from http.cookies import SimpleCookie
from datetime import datetime, timezone
from django.utils.http import http_date
from django.core import signing
import time
from amuse.tokens import otp_token_generator, AuthTokenGenerator
from django.conf import settings

"""
Generate cookies to be used in unit tests.
Required cookies will be set for Django test client.
eg. self.client.cookies = generate_test_client_otp_cookie(self.test_user.pk)
"""


def set_cookie(
    cookie,
    key,
    value='',
    max_age=None,
    expires=None,
    path='/',
    domain=None,
    secure=False,
    httponly=False,
    samesite=None,
):
    """
    Set a cookie.

    ``expires`` can be:
    - a string in the correct format,
    - a naive ``datetime.datetime`` object in UTC,
    - an aware ``datetime.datetime`` object in any time zone.
    If it is a ``datetime.datetime`` object then calculate ``max_age``.
    """
    cookie[key] = value
    if expires is not None:
        if isinstance(expires, datetime.datetime):
            if timezone.is_aware(expires):
                expires = timezone.make_naive(expires, timezone.utc)
            delta = expires - expires.utcnow()
            # Add one second so the date matches exactly (a fraction of
            # time gets lost between converting to a timedelta and
            # then the date string).
            delta = delta + datetime.timedelta(seconds=1)
            # Just set max_age - the max_age logic will set expires.
            expires = None
            max_age = max(0, delta.days * 86400 + delta.seconds)
        else:
            cookie[key]['expires'] = expires
    else:
        cookie[key]['expires'] = ''
    if max_age is not None:
        cookie[key]['max-age'] = int(max_age)
        # IE requires expires, so set it if hasn't been already.
        if not expires:
            cookie[key]['expires'] = http_date(time.time() + max_age)
    if path is not None:
        cookie[key]['path'] = path
    if domain is not None:
        cookie[key]['domain'] = domain
    if secure:
        cookie[key]['secure'] = True
    if httponly:
        cookie[key]['httponly'] = True
    if samesite:
        if samesite.lower() not in ('lax', 'none', 'strict'):
            raise ValueError('samesite must be "lax", "none", or "strict".')
        cookie[key]['samesite'] = samesite
    return cookie


def set_signed_cookie(cookie, key, value, salt='', **kwargs):
    value = signing.get_cookie_signer(salt=key + salt).sign(value)
    return set_cookie(cookie, key, value, **kwargs)


def generate_test_client_otp_cookie(user_id):
    cookie = SimpleCookie()
    token = otp_token_generator.make_token(user_id)
    set_signed_cookie(
        cookie=cookie,
        key='otp',
        value=token,
        secure=False,
        httponly=True,
        samesite='Lax',
        max_age=int(settings.OTP_JWT_EXP_MINUTES) * 60,
    )
    return cookie


def generate_test_client_access_cookie(user_id):
    cookie = SimpleCookie()
    token = AuthTokenGenerator.make_access_token(user_id)
    set_signed_cookie(
        cookie=cookie,
        key=settings.ACCESS_COOKIE_NAME,
        value=token,
        secure=False,
        httponly=True,
        samesite='Lax',
        max_age=int(settings.ACCESS_TOKEN_EXP_MINUTES) * 60,
    )
    return cookie


def generate_test_client_refresh_cookie(user_id):
    cookie = SimpleCookie()
    token = AuthTokenGenerator.make_access_token(user_id)
    set_signed_cookie(
        cookie=cookie,
        key=settings.REFRESH_COOKIE_NAME,
        value=token,
        secure=False,
        httponly=True,
        samesite='Lax',
        max_age=int(settings.REFRESH_TOKEN_EXP_DAYS) * 86400,
    )
    return cookie
