import logging
from datetime import datetime
from enum import IntEnum
from hashlib import sha1
from uuid import uuid4

from django.conf import settings

from amuse.platform import PlatformType
from .tasks import send_impact_event

logger = logging.getLogger(__name__)

CAMPAIGN = 12759


class TrackerID(IntEnum):
    SIGNUP_COMPLETE = 23569
    MUSIC_UPLOAD = 23570
    SUBSCRIPTION_STARTED = 23571


class Tier(IntEnum):
    FREE = 0
    BOOST = 1
    PRO = 2


def generate_event_id():
    return str(uuid4()).replace('-', '')


class Impact(object):
    def __init__(self, user_id, user_email, platform):
        self.event_id = generate_event_id()
        self.user_id = user_id
        self.user_email = user_email
        self.platform = platform

    @staticmethod
    def _get_additional_params(subscription, country):
        card = subscription.plan.get_price_card(country=country)
        currency_code = card.currency.code
        price = str(card.price)

        categories = {Tier.PRO: 'Pro tier', Tier.BOOST: 'Boost tier'}

        names = {Tier.FREE: 'Free', Tier.PRO: 'Pro', Tier.BOOST: 'Boost'}

        tier = subscription.plan.tier
        return {
            'CurrencyCode': currency_code,
            'OrderDiscount': "0",
            'OrderPromoCode': "",
            'ItemSubTotal': price,
            'ItemCategory': categories[tier],
            'ItemSku': tier,
            'ItemQuantity': 1,
            'ItemName': names[tier],
        }

    def _get_common_params(self, tracker_id):
        return {
            'CampaignId': CAMPAIGN,
            'ActionTrackerId': int(tracker_id),
            'EventDate': datetime.utcnow().isoformat(),
            'OrderId': self.event_id,
            'CustomerId': str(self.user_id),
            'CustomerEmail': sha1(self.user_email.encode('utf-8')).hexdigest(),
        }

    def _send(self, tracker_id, params):
        if not settings.IMPACT_ENABLED:
            return

        if self.platform != PlatformType.WEB:
            return

        event_name = TrackerID(tracker_id).name
        logger.info(
            f'Impact: preparing new request, event_id: "{self.event_id}", user_id: "{self.user_id}", event_name: "{event_name}"'
        )

        send_impact_event.delay(self.event_id, params)

    def music_upload(self):
        params = self._get_common_params(TrackerID.MUSIC_UPLOAD)

        self._send(TrackerID.MUSIC_UPLOAD, params)

    def subscription_new_started(self, subscription, country):
        common_params = self._get_common_params(TrackerID.SUBSCRIPTION_STARTED)
        additional_params = self._get_additional_params(subscription, country)

        params = {**common_params, **additional_params}

        self._send(TrackerID.SUBSCRIPTION_STARTED, params)

    def sign_up(self, click_id):
        params = self._get_common_params(TrackerID.SIGNUP_COMPLETE)
        params['ClickId'] = click_id

        self._send(TrackerID.SIGNUP_COMPLETE, params)
