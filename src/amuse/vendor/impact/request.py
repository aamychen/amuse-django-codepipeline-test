import logging
from urllib.parse import urlencode

import requests
import requests.exceptions
from django.conf import settings
from requests.auth import HTTPBasicAuth

logger = logging.getLogger(__name__)

HOST = 'https://api.impact.com'


class ImpactError(Exception):
    pass


def send_request(event_id, params):
    username = settings.IMPACT_SID
    password = settings.IMPACT_PASSWORD

    qs = urlencode(params)

    url = f'{HOST}/Advertisers/{username}/Conversions?{qs}'
    auth = HTTPBasicAuth(username, password)
    res = requests.post(url=url, data={}, auth=auth, timeout=6)

    if res.status_code >= 400:
        raise ImpactError(
            f'Impact: response data error, event_id: "{event_id}", '
            f'status: "{res.status_code}", '
            f'text: "{res.text}"'
        )

    logger.info(f'Impact: response data, event_id: "{event_id}", data: "{res.text}"')
