import logging
from base64 import b85decode
from datetime import timedelta
from json import JSONDecodeError

import jwt
import requests
from django.conf import settings
from django.utils import timezone

from amuse.platform import PlatformType

logger = logging.getLogger(__name__)

name = 'apple'
ACCESS_TOKEN_URL = 'https://appleid.apple.com/auth/token'
AUD = 'https://appleid.apple.com'
SCOPE_SEPARATOR = ','
ID_KEY = 'uid'


def login(platform, access_token, apple_signin_id, *args, **kwargs):
    client_id = _get_client_id(platform)
    client_secret = _get_client_secret(client_id)

    headers = {'content-type': "application/x-www-form-urlencoded"}
    data = {
        'client_id': client_id,
        'client_secret': client_secret,
        'code': access_token,
        'grant_type': 'authorization_code',
    }

    response_dict = _send_request(data=data, headers=headers)

    id_token = response_dict.get('id_token')
    sub = None
    if id_token:
        decoded = jwt.decode(id_token, '', verify=False)
        sub = decoded.get('sub', None)

    return _is_authenticated(sub, apple_signin_id)


def _send_request(data, headers):
    response_dict = {}
    try:
        res = requests.post(ACCESS_TOKEN_URL, data=data, headers=headers)
        response_dict = res.json()
        logger.info(
            'Apple signin response data', extra={'response_data': response_dict}
        )
    except (requests.exceptions.RequestException, JSONDecodeError) as e:
        logger.warning(
            'Apple signin response error data', extra={'apple_response_error': e}
        )
    return response_dict


def _is_authenticated(sub, apple_signin_id):
    if not sub:
        return False

    return sub == apple_signin_id


def _get_client_id(platform):
    if platform == PlatformType.WEB:
        return settings.SOCIAL_AUTH_APPLE_WEB_CLIENT_ID

    return settings.SOCIAL_AUTH_APPLE_CLIENT_ID


def _get_client_secret(client_id):
    headers = {'kid': settings.SOCIAL_AUTH_APPLE_KEY_ID}

    payload = {
        'iss': settings.SOCIAL_AUTH_APPLE_TEAM_ID,
        'iat': timezone.now(),
        'exp': timezone.now() + timedelta(days=180),
        'aud': AUD,
        'sub': client_id,
    }

    secret = b85decode(settings.SOCIAL_AUTH_APPLE_PRIVATE_KEY).decode('utf-8')

    client_secret = jwt.encode(
        payload, secret, algorithm='ES256', headers=headers
    ).decode("utf-8")

    return client_secret
