from decimal import Decimal

from django.conf import settings
from rest_framework.exceptions import APIException, ValidationError
from waffle import flag_is_active

from amuse.analytics import login_succeeded
from amuse.platform import PlatformType
from amuse.utils import (
    parse_client_data,
    parse_client_name,
    generate_password_reset_url,
)
from countries.models import Country
from releases.models import RoyaltySplit
from users.models import ArtistV2, UserArtistRole


class NotImplementedException(APIException):
    status_code = 501
    default_detail = "API version not implemented."
    default_code = "not_implemented"


def create_legacy_royalty_split(song, user):
    return RoyaltySplit.objects.create(
        song=song,
        user=user,
        rate=Decimal("1.00"),
        status=RoyaltySplit.STATUS_ACTIVE,
        start_date=None,
        revision=1,
    )


def get_artist(artist_id, user_id):
    try:
        artist = ArtistV2.objects.get(pk=artist_id)
    except ArtistV2.DoesNotExist:
        raise ValidationError('Invalid artist')
    if not artist.is_accessible_by(
        user_id, [UserArtistRole.ADMIN, UserArtistRole.OWNER, UserArtistRole.SUPERADMIN]
    ):
        raise ValidationError('Invalid artist')
    return artist


def format_otp_message(mfa_code, platform):
    base_message = f'Your Amuse 2FA code is'
    if platform == PlatformType.ANDROID:
        return f'{base_message} {mfa_code}\n\n{settings.ANDROID_APP_MFA_HASH}'

    return f'{base_message} {mfa_code[:3]} {mfa_code[3:]}'


def send_login_succeeded(request, user):
    client_data = parse_client_data(request)
    if client_data['country']:
        country = Country.objects.filter(code=client_data['country']).first()
        client_data['country'] = country.name if country else client_data['country']

    client_data['url'] = generate_password_reset_url(user)
    login_succeeded(user, client_data)


def is_2fa_enabled_for_client(request):
    """2FA can be enabled/disabled for Android/iOS/web through the Waffle
    flags 2FA-android, 2FA-ios, 2FA-web. There is also 2FA-other which is
    for clients with non-conforming user agent (e.g. DDOS, web crawler).
    """
    client_name = parse_client_name(request.META.get('HTTP_USER_AGENT') or '')
    return flag_is_active(request, f'2FA-{client_name}')


def is_2fa_enabled(request, user):
    is_apple_signin = bool(user.apple_signin_id)
    if is_apple_signin:
        # for apple social login users, sms-code check is disabled always.
        return False

    if not is_2fa_enabled_for_client(request):
        return False

    if user.otp_enabled:
        if not user.phone:
            # super edge case
            raise ValidationError(
                {'phone': 'Missing phone number. Contact customer support.'}
            )
        return True

    return False
