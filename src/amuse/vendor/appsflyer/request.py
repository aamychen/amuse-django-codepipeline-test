import logging

from requests import sessions

logger = logging.getLogger(__name__)
session = sessions.Session()


def send_request(event_id, url, body, headers={}):
    event_name = body.get('eventName')
    headers = {
        **headers,
        **{'Accept-Encoding': 'application/json', 'Content-Type': 'application/json'},
    }

    res = session.post(url, json=body, headers=headers, timeout=5)

    if res.status_code >= 400:
        raise Exception(
            f'AppsFlyer: response data error, event_id: "{event_id}", event_name: "{event_name}", '
            f'status: "{res.status_code}", '
            f'text: "{res.text}"'
        )

    logger.info(
        f'AppsFlyer: response data, event_id: "{event_id}", event_name: "{event_name}", data: "{res.text}"'
    )
