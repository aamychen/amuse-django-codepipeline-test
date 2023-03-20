from hashlib import sha1
from unittest.mock import patch

from django.test import override_settings
from django.utils import timezone
from freezegun import freeze_time

from amuse.platform import PlatformType
from amuse.tests.test_api.base import AmuseAPITestCase
from amuse.vendor.impact import Impact
from countries.tests.factories import CountryFactory, CurrencyFactory
from subscriptions.tests.factories import (
    PriceCardFactory,
    SubscriptionPlanFactory,
    SubscriptionFactory,
)
from users.tests.factories import UserFactory


@override_settings(
    IMPACT_ENABLED=True, IMPACT_SID='FAKE-SID', IMPACT_PASSWORD='FAKE-PASSWORD'
)
class TestCaseImpactEvents(AmuseAPITestCase):
    def setUp(self):
        self.user = UserFactory()

    @patch('amuse.vendor.impact.events.generate_event_id', return_value='uuid123')
    @patch('amuse.vendor.impact.events.logger.info')
    @patch('amuse.vendor.impact.events.send_impact_event.delay')
    def test_sign_up(self, mock_delay, mock_info, mock_uuid):
        with freeze_time("2020-01-21"):
            Impact(self.user.id, self.user.email, PlatformType.WEB).sign_up('click123')

        params = {
            'CampaignId': 12759,
            'ActionTrackerId': 23569,
            'EventDate': '2020-01-21T00:00:00',
            'OrderId': 'uuid123',
            'CustomerId': str(self.user.id),
            'CustomerEmail': sha1(self.user.email.encode('utf-8')).hexdigest(),
            'ClickId': 'click123',
        }

        mock_delay.assert_called_once_with('uuid123', params)
        mock_info.assert_called_once_with(
            f'Impact: preparing new request, event_id: "uuid123", user_id: "{self.user.id}", event_name: "SIGNUP_COMPLETE"'
        )

    @patch('amuse.vendor.impact.events.generate_event_id', return_value='uuid123')
    @patch('amuse.vendor.impact.events.logger.info')
    @patch('amuse.vendor.impact.events.send_impact_event.delay')
    def test_music_upload(self, mock_delay, mock_info, mock_uuid):
        with freeze_time("2020-01-21"):
            Impact(self.user.id, self.user.email, PlatformType.WEB).music_upload()

        params = {
            'CampaignId': 12759,
            'ActionTrackerId': 23570,
            'EventDate': '2020-01-21T00:00:00',
            'OrderId': 'uuid123',
            'CustomerId': str(self.user.id),
            'CustomerEmail': sha1(self.user.email.encode('utf-8')).hexdigest(),
        }

        mock_delay.assert_called_once_with('uuid123', params)
        mock_info.assert_called_once_with(
            f'Impact: preparing new request, event_id: "uuid123", user_id: "{self.user.id}", event_name: "MUSIC_UPLOAD"'
        )

    @patch('amuse.vendor.impact.events.logger.info')
    @patch('amuse.vendor.impact.events.send_impact_event.delay')
    def test_do_not_send_for_other_platform_than_web(self, mock_delay, mock_info):
        Impact(1, 'aaa@aaa.com', PlatformType.IOS).sign_up('click123')

        self.assertEqual(0, mock_delay.call_count)
        self.assertEqual(0, mock_info.call_count)


@override_settings(IMPACT_ENABLED=False)
class TestCaseImpactDisabledEvents(AmuseAPITestCase):
    def setUp(self):
        self.user = UserFactory()

    @patch('amuse.vendor.impact.events.logger.info')
    @patch('amuse.vendor.impact.events.send_impact_event.delay')
    def test_sign_up(self, mock_delay, mock_info):
        Impact(1, 'aaa@aaa.com', PlatformType.WEB).sign_up('click123')

        self.assertEqual(0, mock_delay.call_count)
        self.assertEqual(0, mock_info.call_count)

    @patch('amuse.vendor.impact.events.logger.info')
    @patch('amuse.vendor.impact.events.send_impact_event.delay')
    def test_music_upload(self, mock_delay, mock_info):
        Impact(1, 'aaa@aaa.com', PlatformType.WEB).music_upload()

        self.assertEqual(0, mock_delay.call_count)
        self.assertEqual(0, mock_info.call_count)


@override_settings(
    IMPACT_ENABLED=True, IMPACT_SID='FAKE-SID', IMPACT_PASSWORD='FAKE-PASSWORD'
)
class TestCaseSubscriptionNewStarted(AmuseAPITestCase):
    def setUp(self):
        self.user = UserFactory()
        self.plan = SubscriptionPlanFactory(create_card=False)
        self.subscription = SubscriptionFactory(
            user=self.user,
            plan=self.plan,
            grace_period_until=timezone.now(),
            valid_until=timezone.now(),
        )
        self.currency = CurrencyFactory(code='USD')
        self.country = CountryFactory(code='US')
        self.card = PriceCardFactory(
            price=12.34,
            plan=self.plan,
            currency=self.currency,
            countries=[self.country],
        )

    @patch('amuse.vendor.impact.events.generate_event_id', return_value='uuid123')
    @patch('amuse.vendor.impact.events.logger.info')
    @patch('amuse.vendor.impact.events.send_impact_event.delay')
    def test_subscription_new_started(self, mock_delay, mock_info, mock_uuid):
        with freeze_time("2020-01-21"):
            Impact(
                self.user.id, self.user.email, PlatformType.WEB
            ).subscription_new_started(self.subscription, self.country)

        params = {
            'CampaignId': 12759,
            'ActionTrackerId': 23571,
            'EventDate': '2020-01-21T00:00:00',
            'OrderId': 'uuid123',
            'CustomerId': str(self.user.id),
            'CustomerEmail': sha1(self.user.email.encode('utf-8')).hexdigest(),
            'CurrencyCode': 'USD',
            'OrderDiscount': "0",
            'OrderPromoCode': "",
            'ItemSubTotal': '12.34',
            'ItemCategory': 'Pro tier',
            'ItemSku': 2,
            'ItemQuantity': 1,
            'ItemName': 'Pro',
        }

        mock_delay.assert_called_once_with('uuid123', params)
        mock_info.assert_called_once_with(
            f'Impact: preparing new request, event_id: "uuid123", user_id: "{str(self.user.id)}", event_name: "SUBSCRIPTION_STARTED"'
        )
