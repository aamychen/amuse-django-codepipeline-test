# https://support.appsflyer.com/hc/en-us/articles/207034486-Server-to-server-events-API-for-mobile-S2S-mobile-
import json
import logging
from datetime import datetime

from django.conf import settings

from .helpers import generate_event_id
from .tasks import send_event

logger = logging.getLogger(__name__)


def _get_event_value(data):
    # https://support.appsflyer.com/hc/en-us/articles/207034486-Server-to-server-events-API-for-mobile-S2S-mobile-#s2s-api-facts
    if data is None:
        return ''

    if data == {}:
        return ''

    return json.dumps(data)


def _get_event_time():
    # See https://support.appsflyer.com/hc/en-us/articles/207034486-Server-to-server-events-API-for-mobile-S2S-mobile-#eventtime-10
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]


def _send_s2s_ios(device, user_id, event_name, data={}):
    event_id = generate_event_id()

    headers = {'authentication': settings.APPSFLYER_DEV_KEY}

    ip = data.get('ip')
    currency_code = data.get('currency')

    payload = {
        'appsflyer_id': device.appsflyer_id,
        'customer_user_id': user_id,
        'idfa': device.idfa,
        'idfv': device.idfv,
        'eventName': event_name,
        'eventValue': _get_event_value(data),
        'ip': ip,
        'eventCurrency': currency_code,
        'eventTime': _get_event_time(),
    }

    logger.info(
        f'AppsFlyer: preparing new ios request, event_id: "{event_id}", '
        f'eventName: "{event_name}", '
        f'user_id: "{user_id}", '
        f'eventCurrency: "{currency_code}"'
    )

    url = f'https://api2.appsflyer.com/inappevent/{settings.APPSFLYER_IOS_APP_ID}'
    send_event.delay(event_id, url, payload, headers)


def _send_s2s_android(device, user_id, event_name, data={}):
    event_id = generate_event_id()

    headers = {'authentication': settings.APPSFLYER_DEV_KEY}

    ip = data.get('ip')
    currency_code = data.get('currency')

    payload = {
        'appsflyer_id': device.appsflyer_id,
        'customer_user_id': user_id,
        'advertising_id': device.aaid,
        'oaid': device.oaid,
        'imei': device.imei,
        'eventName': event_name,
        'eventValue': _get_event_value(data),
        'ip': ip,
        'eventCurrency': currency_code,
        'eventTime': _get_event_time(),
    }

    logger.info(
        f'AppsFlyer: preparing new android request, event_id: "{event_id}", '
        f'eventName: "{event_name}", '
        f'user_id: "{user_id}", '
        f'eventCurrency: "{currency_code}"'
    )

    url = f'https://api2.appsflyer.com/inappevent/{settings.APPSFLYER_ANDROID_APP_ID}'
    send_event.delay(event_id, url, payload, headers)
