from typing import Optional

from django.conf import settings
from rest_framework.exceptions import ValidationError
from twilio.base.exceptions import TwilioRestException
from twilio.rest import Client

from amuse.utils import (
    FakePhoneNumberError,
    InvalidPhoneNumberError,
    format_phonenumber,
)

WELCOME_MSG = 'Welcome to Amuse! Follow this link to download our app and get your music career started – http://bit.ly/install-amuse'


class TwilioException(Exception):
    def __init__(self, message: str):
        self.message = message


class TwilioClient:
    def __init__(self):
        self.sid = settings.TWILIO_SID
        self.token = settings.TWILIO_TOKEN
        self.from_ = settings.TWILIO_FROM
        self.client = Client(self.sid, self.token)


class TwilioSMS(TwilioClient):
    def send(self, phone: str, message: str):
        return self.client.messages.create(body=message, to=phone, from_=self.from_)

    def lookup(self, phone: str):
        return self.client.lookups.phone_numbers(phone).fetch(type=['carrier'])


def send_download_link(number: str):
    sms = TwilioSMS()

    try:
        return sms.send(number, WELCOME_MSG)
    except TwilioRestException as t_rex:
        raise TwilioException(message=t_rex.msg)


def send_sms_code(number: str, formatted_message):
    sms = TwilioSMS()
    try:
        sms.send(number, formatted_message)
    except TwilioRestException as e:
        raise TwilioException(message=e.msg)


def is_allowed_phone(number: str):
    '''Disallow VoIP numbers and landlines'''
    sms = TwilioSMS()
    try:
        number_info = sms.lookup(number)
        # see: https://www.twilio.com/docs/lookup/api#phone-number-type-values
        return number_info.country_code, number_info.carrier['type'] in ('mobile', None)
    except TwilioRestException as e:
        raise TwilioException(message=e.msg)


def validate_phone(phone):
    if not phone or not phone.strip():
        raise ValidationError({'phone': 'Invalid phone number'})

    # Validate phone carrier type
    try:
        country_code, is_allowed = is_allowed_phone(phone)
        if not is_allowed:
            raise ValidationError({'phone': 'Invalid phone number'})
        # Validate phone number format
        phone = format_phonenumber(phone, country_code)
    except TwilioException:
        raise ValidationError({'phone': 'Phone lookup failed'})
    except (FakePhoneNumberError, InvalidPhoneNumberError):
        raise ValidationError({'phone': 'Invalid phone number'})
    return phone
