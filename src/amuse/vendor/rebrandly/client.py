import requests
import logging
from django.conf import settings

HOST = 'api.rebrandly.com'

logger = logging.getLogger(__name__)


class RebrandlyException(Exception):
    pass


class Rebrandly:
    def __init__(self):
        self.url = 'https://' + HOST + '/v1/links'
        self.apps_url = 'https://' + HOST + '/v1/apps'
        self.api_key = settings.REBRANDLY_API_KEY
        self.link_domain = settings.REBRANDLY_DOMAIN
        if settings.REBRANDLY_APP_IDS:
            self.app_ids = settings.REBRANDLY_APP_IDS.split(',')
        else:
            self.app_ids = []

    def generate_link(self, original_link):
        try:
            if not settings.REBRANDLY_ENABLED:
                return original_link

            response = requests.post(
                self.url,
                json={
                    "destination": original_link,
                    "domain": {"fullName": self.link_domain},
                },
                headers={'Content-Type': 'application/json', 'apikey': self.api_key},
            )

            if response.status_code not in [200, 201]:
                raise RebrandlyException(
                    f'Rebrandly {self.url} respond with '
                    f'code={response.status_code}, '
                    f'reason={response.reason}, '
                    f'text={response.text}'
                )

            data = response.json()
            for app_id in self.app_ids:
                self.link_app(original_link, data['id'], app_id)

            return data['shortUrl']
        except Exception as e:
            logger.exception(e)
            return original_link

    def link_app(self, original_link, link_id, app_id):
        try:
            response = requests.post(
                self.url + '/' + link_id + '/apps/' + app_id,
                json={'path': original_link.replace('https://', '')},
                headers={'Content-Type': 'application/json', 'apikey': self.api_key},
            )
            if response.status_code != 200:
                raise RebrandlyException(
                    f'Rebrandly {self.url} respond with '
                    f'code={response.status_code}, '
                    f'reason={response.reason}, '
                    f'text={response.text}'
                )
        except Exception as e:
            logger.exception(e)
