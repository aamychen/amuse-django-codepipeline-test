import base64
import functools
import logging
import random
import re
import string
import json
from decimal import ROUND_HALF_UP, Decimal

import requests
from django.conf import settings
from django.core.handlers.wsgi import WSGIRequest
from django.urls import get_resolver
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from django.utils.text import Truncator

import phonenumbers
from amuse.settings.constants import ARTIST_NAME_MATCH_RATIO
from amuse.tokens import password_reset_token_generator
from fuzzywuzzy import fuzz
from phonenumbers.phonenumberutil import NumberParseException
from storages.backends.s3boto3 import S3Boto3Storage, S3Boto3StorageFile
from ua_parser import user_agent_parser
from waffle import switch_is_active


logger = logging.getLogger("amuse")
logger.propagate = False


CLIENT_ANDROID = 1
CLIENT_IOS = 2
CLIENT_WEB = 3
CLIENT_OTHER = 4
CLIENT_OPTIONS = {
    CLIENT_ANDROID: 'android',
    CLIENT_IOS: 'ios',
    CLIENT_WEB: 'web',
    CLIENT_OTHER: 'other',
}


def download_to_bucket(url, bucket, key, headers=None):
    """
    Download a file straight to an S3 bucket.
    :param url: URL
    :param bucket: Bucket name
    :param key: Bucket path to save file at
    :param headers Google api headers
    :return: None
    """
    storage = S3Boto3Storage(bucket_name=bucket)
    with requests.get(url, headers=headers, stream=True, timeout=(5, 180)) as r:
        r.raise_for_status()
        # Stream file contents to S3 by writing chunks
        with S3Boto3StorageFile(name=key, mode='w', storage=storage) as s3file:
            # Use chunks provided by server if the response is chunked, else 1MB
            for chunk in r.iter_content(
                chunk_size=None if r.raw.chunked else 1024 * 1024
            ):
                if not chunk:
                    break
                s3file.write(chunk)


def get_ip_address(request):
    xff = request.META.get('HTTP_X_FORWARDED_FOR')
    if xff:
        return xff.split(',')[0]
    return request.META.get('REMOTE_ADDR')


def get_random_email():
    letters = string.ascii_lowercase
    first_part = ''.join(random.choice(letters) for _ in range(8))
    return first_part + '@example.com'


def convert_to_positive_and_round(
    decimal_value, precision='.01', rounding=ROUND_HALF_UP
):
    return abs(decimal_value).quantize(Decimal(precision), rounding=rounding)


def format_phonenumber(phone_number, country_code):
    """
    Formats any valid phonenumber to E164 format. Will fail on fake and empty
    phone numbers. A countrycode mismatch will be overridden by the `+46` in the number.
    """
    try:
        parsed_phone = phonenumbers.parse(phone_number, country_code)

        if not phonenumbers.is_valid_number(parsed_phone):
            raise FakePhoneNumberError

        formatted_phone = phonenumbers.format_number(
            parsed_phone, phonenumbers.PhoneNumberFormat.E164
        )
    except NumberParseException:
        raise InvalidPhoneNumberError

    return formatted_phone


def parse_client_version(user_agent):
    m = re.search(r'^amuse-(android|ios|web)\/(.*?);', user_agent, re.IGNORECASE)
    if m:
        clients = {v: k for k, v in CLIENT_OPTIONS.items()}
        return (clients[m.group(1).lower()], m.group(2))
    return (CLIENT_OTHER, 'N/A')


def parse_client_name(user_agent):
    client = parse_client_version(user_agent or '')[0]
    client_name = CLIENT_OPTIONS.get(client)
    return client_name


def parse_client_data(request):
    detected_country = request.META.get('HTTP_CF_IPCOUNTRY')
    ip = get_ip_address(request)

    raw_user_agent = request.META.get('HTTP_USER_AGENT') or ''
    user_agent = user_agent_parser.Parse(raw_user_agent)
    if raw_user_agent.startswith('amuse-'):
        ua = f"Amuse for {'iOS' if raw_user_agent.startswith('amuse-iOS') else 'Android'}"
        user_agent['user_agent']['family'] = ua

    data = {
        'country': detected_country,
        'ip': ip,
        'device_family': user_agent['device']['family'],
        'os_family': user_agent['os']['family'],
        'user_agent_family': user_agent['user_agent']['family'],
    }

    return data


class FakePhoneNumberError(Exception):
    pass


class InvalidPhoneNumberError(Exception):
    pass


def match_strings(string_a, string_b):
    lower_a = string_a.lower() if string_a else ""
    lower_b = string_b.lower() if string_b else ""
    ratio = fuzz.token_sort_ratio(lower_a, lower_b)
    if ratio >= ARTIST_NAME_MATCH_RATIO:
        return True
    return False


def chunks(l, n):
    """Yield successive n-sized chunks from l."""
    for i in range(0, len(l), n):
        yield l[i : i + n]


class MapPgResults(object):
    def __init__(self, cursor, registro):
        for attr, val in zip((d[0] for d in cursor.description), registro):
            setattr(self, attr, val)


def log_func(max_length=100):
    def _log_func(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            str_args = Truncator(args.__str__()).chars(max_length)
            str_kwargs = Truncator(kwargs.__str__()).chars(max_length)

            logger.info(
                "Start %s(args=%s, kwargs=%s)" % (func.__name__, str_args, str_kwargs)
            )
            value = func(*args, **kwargs)
            str_value = Truncator(value.__str__()).chars(max_length)

            logger.info("End %s with return value %s" % (func.__name__, str_value))
            return value

        return wrapper

    return _log_func


def rename_key(data, old_key, new_key):
    data[new_key] = data[old_key]
    del data[old_key]
    return data


def resolve_naming_conflicts(record):
    """This function will purify the logging record by resolving naming conflicts."""
    if (
        (
            record.method == 'GET'
            and record.response != {}
            and not 'detail' in record.response
        )
        and (
            record.uri == '/royalty-splits'
            or record.uri.startswith('/releases/')
            or record.uri.startswith('/users')
            or record.uri.startswith('/artists')
        )
        or (
            record.method == 'POST'
            and (
                record.uri.startswith('/artists/')
                or record.uri.startswith('/releases/')
            )
        )
        or (record.method == 'PATCH' and record.uri.startswith('/releases/'))
    ):
        if (
            record.uri.startswith('/users')
            and not record.uri.endswith('/transactions/')
            and 'country' in record.response
        ):
            record.response = rename_key(record.response, 'country', 'country_code')
        elif record.uri.startswith('/users') and record.uri.endswith('/transactions/'):
            record.response['transactions'] = [
                rename_key(transaction, 'status', 'status_string')
                for transaction in record.response['transactions']
            ]
        elif record.uri.startswith('/releases/'):
            if isinstance(record.response, dict):
                record.response = rename_key(record.response, 'status', 'status_string')
            else:
                record.response = [
                    rename_key(release, 'status', 'status_string')
                    for release in record.response
                ]
        elif record.uri.startswith('/artists') and not record.uri.endswith('/team/'):
            if isinstance(record.response, dict):
                record.response = rename_key(
                    record.response, 'main_artist_profile', 'is_main_artist_profile'
                )
            else:
                record.response = [
                    rename_key(artist, 'main_artist_profile', 'is_main_artist_profile')
                    for artist in record.response
                ]
        else:
            # Which means record.uri == '/royalty-splits'
            record.response = [
                rename_key(royalty_split, 'cover_art', 'cover_art_url')
                for royalty_split in record.response
            ]

    return record


def parsed_django_request_string(django_request_string):
    cleaned_request_string = django_request_string[14:]
    method, request_url = cleaned_request_string.split()

    return {'method': method, 'request_url': request_url[1:-2]}


def generate_password_reset_url(user):
    url = '%s%s' % (
        settings.APP_URL,
        get_resolver().reverse(
            'password_reset_confirm',
            uidb64=urlsafe_base64_encode(force_bytes(user.pk)),
            token=password_reset_token_generator.make_token(user),
        ),
    )

    return url


def is_authenticated_http(request, expected_username, expected_password):
    '''Verify HTTP basic authentication'''
    is_valid = False
    if 'HTTP_AUTHORIZATION' in request.META:
        auth = request.META['HTTP_AUTHORIZATION'].split()
        if len(auth) == 2:
            if auth[0].lower() == 'basic':
                decoded_auth = base64.b64decode(auth[1]).decode('utf-8')
                username, password = decoded_auth.split(':')
                is_valid = (
                    username == expected_username and password == expected_password
                )
    return is_valid


def phone_region_code_from_number(phone_number):
    try:
        pn = phonenumbers.parse(phone_number)
        return (
            phonenumbers.region_code_for_number(pn)
            or phonenumbers.phonenumberutil.UNKNOWN_REGION
        )
    except phonenumbers.phonenumberutil.NumberParseException:
        return phonenumbers.phonenumberutil.UNKNOWN_REGION


def is_verify_phone_mismatch_country_blocked(request):
    ip_country = parse_client_data(request)["country"]
    phone_country = phone_region_code_from_number(request.data.get("phone"))
    return (
        switch_is_active(f"sinch:block-mismatch:{phone_country.lower()}")
        and ip_country != phone_country
    )


def parseJSONField(value):
    '''
    JSONField when retured from db is dict except in case of unit test when str is
    returned. This method is workaround for that inconsistency
    :param returned_value:
    :return: dict
    '''
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        return json.loads(value)


def get_client_captcha_token(request: WSGIRequest, form: str = False) -> str:
    """
    Clients will be sending captcha token in request header for api calls, in case of
    Djanog forms token can  be sent as hidden form field
    :param request: WSGIRequest
    :param form: bool indicating is captcha token in form data
    :return: str reCAPTCHA token or None
    """
    if form:
        return request.POST.get(settings.CAPTCHA_BODY_KEY)
    return request.META.get(settings.CAPTCHA_HEADER_KEY)


def check_swedish_pnr(pnr):
    if pnr is None:
        return False
    digits = [int(d) for d in re.sub(r'\D', '', pnr)][-10:]
    if len(digits) != 10:
        return False
    month_int = int(''.join(map(str, digits[2:4])))
    day_int = int(''.join(map(str, digits[4:6])))
    # check month
    if month_int > 12 or month_int == 0:
        return False
    # check day of month
    if day_int > 31 or day_int == 0:
        return False
    even_digitsum = sum(x if x < 5 else x - 9 for x in digits[::2])
    return 0 == sum(digits, even_digitsum) % 10
