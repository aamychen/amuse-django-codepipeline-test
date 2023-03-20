import logging

from django.conf import settings

from .helpers import generate_event_id
from .request import send_request

logger = logging.getLogger(__name__)


def send_set_cuid(user_id, af_user_id):
    if not settings.APPSFLYER_ENABLED:
        return

    event_id = generate_event_id()
    dev_key = settings.APPSFLYER_WEB_DEV_KEY

    payload = {
        'customerUserId': str(user_id),
        'afUserId': af_user_id,
        'webDevKey': dev_key,
    }

    logger.info(
        f'AppsFlyer: cui request, event_id: "{event_id}", '
        f'af_user_id: "{af_user_id}", '
        f'user_id: "{user_id}"'
    )

    url = (
        f'https://webs2s.appsflyer.com/v1/{settings.APPSFLYER_BRAND_BUNDLE_ID}/setcuid'
    )
    send_request(event_id, url, payload)
