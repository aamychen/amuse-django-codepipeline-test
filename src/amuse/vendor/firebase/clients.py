# -*- coding: utf-8 -*-

import os
import requests
import json

from django.conf import settings

from .models import Payload, Notification


API_URL = getattr(settings, 'FIREBASE_API_URL', None)
API_KEY = getattr(settings, 'FIREBASE_API_SERVER_KEY', None)
TIMEOUT = 5


class BaseLegacyClient:
    def __init__(self, api_url=API_URL, api_key=API_KEY):
        self.api_url = api_url
        self.api_key = api_key

        self.headers = {
            'Authorization': 'key={0}'.format(self.api_key),
            'Content-Type': 'application/json',
        }

    def json_default(self, object):
        return object.__dict__

    def json_convert(self, object, pretty=False):
        if pretty:
            return json.dumps(object, indent=2, default=self.json_default)
        else:
            return json.dumps(object, default=self.json_default)

    def post(self, data):
        try:
            return requests.post(
                self.api_url, headers=self.headers, data=data, timeout=TIMEOUT
            )
        except:
            raise


class CloudMessagingClient(BaseLegacyClient):
    def send(self, payload):
        json_payload = self.json_convert(payload)
        return self.post(json_payload)
