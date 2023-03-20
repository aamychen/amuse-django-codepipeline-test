# https://support.appsflyer.com/hc/en-us/articles/360006997298-
import logging
from datetime import datetime, timezone

from django.conf import settings
from django.utils import timezone

from .helpers import generate_event_id
from .tasks import send_event

logger = logging.getLogger(__name__)


def _send_s2s_web(device, user_id, event_name, data={}):
    event_id = generate_event_id()
    dev_key = settings.APPSFLYER_WEB_DEV_KEY

    ip = data.pop('ip', None)
    currency_code = data.get('currency')
    plan_name = data.get('plan_name')
    price = _get_price(data)

    # https://support.appsflyer.com/hc/en-us/articles/360006997298-#webdevkey-3
    payload = {
        'customerUserId': str(user_id),
        'afUserId': device.appsflyer_id,
        'webDevKey': dev_key,
        'eventType': 'EVENT',
        'timestamp': _get_timestamp(),
        'eventName': event_name,
        'ip': ip,
        'eventRevenueCurrency': currency_code,
        'eventRevenue': price,
        'eventCategory': plan_name,
        'eventValue': {'purchase': data},
    }

    logger.info(
        f'AppsFlyer: preparing new webapp request, event_id: "{event_id}", '
        f'eventName: "{event_name}", '
        f'user_id: "{user_id}", '
        f'eventCurrency: "{currency_code}"'
    )

    url = f'https://webs2s.appsflyer.com/v1/{settings.APPSFLYER_BRAND_BUNDLE_ID}/event'
    send_event.delay(event_id, url, payload, {})


def _get_price(data):
    price = data.get('price')
    if price is None:
        return None

    return float(price)


def _get_timestamp():
    return int(datetime.now(tz=timezone.utc).timestamp() * 1000)
