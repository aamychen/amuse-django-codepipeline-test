from waffle import switch_is_active

from amuse.utils import phone_region_code_from_number
from amuse.vendor.sinch.client import Sinch


def should_use_sinch(number):
    country = phone_region_code_from_number(number).lower()
    # Temporary workaround for NZ until we have a deal with Sinch
    # / brodd 2022-02-21
    if country == "nz" and not switch_is_active("sinch:active:nz"):
        return False
    return switch_is_active("sinch:active:ww")


def send_sms(to_number, message):
    client = Sinch()
    return client.sms(to_number, message)


def send_otp_sms(to_number, formatted_message):
    return send_sms(to_number, formatted_message)
