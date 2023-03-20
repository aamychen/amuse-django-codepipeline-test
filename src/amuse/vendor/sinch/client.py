import logging

import requests
from amuse.utils import phone_region_code_from_number
from django.conf import settings

logger = logging.getLogger(__name__)


class Sinch:
    def __init__(self):
        self.us = Client(
            settings.SINCH_US_SERVICE_PLAN_ID,
            settings.SINCH_US_API_TOKEN,
            settings.SINCH_US_SENDER,
        )
        self.ca = Client(
            settings.SINCH_CA_SERVICE_PLAN_ID,
            settings.SINCH_CA_API_TOKEN,
            settings.SINCH_CA_SENDER,
        )
        self.ww = Client(
            settings.SINCH_WW_SERVICE_PLAN_ID,
            settings.SINCH_WW_API_TOKEN,
            settings.SINCH_WW_SENDER,
        )

    def sms(self, to_number, message):
        country = phone_region_code_from_number(to_number)
        if country == "CA":
            return self.ca.sms(to_number, message)
        elif country in ("US", "PR"):
            return self.us.sms(to_number, message)
        else:
            return self.ww.sms(to_number, message)


class Client:
    def __init__(self, service_plan_id, api_token, sender):
        self.service_plan_id = service_plan_id
        self.api_token = api_token
        self.sender = sender

    def sms(self, to_number, message):
        endpoint = settings.SINCH_BATCH_API_ENDPOINT % self.service_plan_id
        headers = {"Authorization": f"Bearer {self.api_token}"}
        payload = {"from": self.sender, "to": [to_number], "body": message}
        response = requests.post(endpoint, headers=headers, json=payload)
        if response.status_code != 201:
            logger.error(
                "Sinch failed to send SMS with status %s response: %s",
                response.status_code,
                response.text,
            )
            return False
        return True
