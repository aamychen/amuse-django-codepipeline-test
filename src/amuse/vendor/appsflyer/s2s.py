import logging

from django.conf import settings

from .helpers import are_all_equal_to_none
from .s2s_mobile import _send_s2s_ios, _send_s2s_android
from .s2s_web import _send_s2s_web


DEVICE_WEB = 0
DEVICE_IOS = 1
DEVICE_ANDROID = 2

logger = logging.getLogger(__name__)


def _get_device_type(device):
    if not are_all_equal_to_none([device.idfa, device.idfv]):
        return DEVICE_IOS

    if not are_all_equal_to_none([device.aaid, device.oaid, device.imei]):
        return DEVICE_ANDROID

    return DEVICE_WEB


def send_s2s(device, user_id, event_name, data={}):
    if not settings.APPSFLYER_ENABLED:
        return

    if device is None:
        logger.warning(
            f'AppsFlyer: s2s event will not be sent because device is missing, '
            f'eventName: "{event_name}", '
            f'user_id: "{user_id}"'
        )
        return

    device_type = _get_device_type(device)

    if device_type == DEVICE_IOS:
        _send_s2s_ios(device, user_id, event_name, data)
        return

    if device_type == DEVICE_ANDROID:
        _send_s2s_android(device, user_id, event_name, data)
        return

    _send_s2s_web(device, user_id, event_name, data)
