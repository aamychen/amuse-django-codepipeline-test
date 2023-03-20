from unittest.mock import patch

from django.test import override_settings
from freezegun import freeze_time

from amuse.tests.test_api.base import AmuseAPITestCase
from amuse.vendor.appsflyer.s2s_web import _send_s2s_web, _get_price
from users.tests.factories import AppsflyerDeviceFactory


@override_settings(
    APPSFLYER_ENABLED=True,
    APPSFLYER_IOS_APP_ID='FAKE-IOS-APP-ID',
    APPSFLYER_ANDROID_APP_ID='FAKE-ANDROID-APP-ID',
    APPSFLYER_DEV_KEY='FAKE-DEV-KEY',
    APPSFLYER_BRAND_BUNDLE_ID='FAKE-BUNDLE-ID',
    APPSFLYER_WEB_DEV_KEY='FAKE-WEB-DEV-KEY',
)
class TestCaseS2SWeb(AmuseAPITestCase):
    @patch('amuse.vendor.appsflyer.s2s_web.generate_event_id', return_value='123')
    @patch('amuse.vendor.appsflyer.s2s_web.send_event.delay')
    def test_send_web_s2s(self, mock_send, mock_generate_event_id):
        device = AppsflyerDeviceFactory(appsflyer_id='123')
        with freeze_time("2020-01-15 06:10:12"):
            _send_s2s_web(
                device=device,
                user_id=1,
                event_name='random-event',
                data={
                    'currency': 'USD',
                    'price': '12.34',
                    'plan_name': 'monthtly',
                    'ip': '123.123.0.1',
                },
            )

        mock_send.assert_called_once_with(
            '123',
            'https://webs2s.appsflyer.com/v1/FAKE-BUNDLE-ID/event',
            {
                'customerUserId': '1',
                'afUserId': '123',
                'webDevKey': 'FAKE-WEB-DEV-KEY',
                'eventType': 'EVENT',
                'timestamp': 1579068612000,
                'eventName': 'random-event',
                'eventRevenueCurrency': 'USD',
                'eventRevenue': 12.34,
                'eventCategory': 'monthtly',
                'ip': '123.123.0.1',
                'eventValue': {
                    'purchase': {
                        'plan_name': 'monthtly',
                        'price': '12.34',
                        'currency': 'USD',
                    }
                },
            },
            {},
        )

    def test_get_price(self):
        result = _get_price({})
        self.assertIsNone(result)

        result = _get_price({'price': '12.34'})
        self.assertEqual(float('12.34'), result)

        result = _get_price({'price': 12.345})
        self.assertEqual(float(12.345), result)
