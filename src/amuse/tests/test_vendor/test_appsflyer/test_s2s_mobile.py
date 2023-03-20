from unittest.mock import patch

from django.test import override_settings
from freezegun import freeze_time

from amuse.tests.test_api.base import AmuseAPITestCase
from amuse.vendor.appsflyer.s2s_mobile import _send_s2s_android, _send_s2s_ios
from users.tests.factories import AppsflyerDeviceFactory


@override_settings(
    APPSFLYER_ENABLED=True,
    APPSFLYER_IOS_APP_ID='FAKE-IOS-APP-ID',
    APPSFLYER_ANDROID_APP_ID='FAKE-ANDROID-APP-ID',
    APPSFLYER_DEV_KEY='FAKE-DEV-KEY',
    APPSFLYER_BRAND_BUNDLE_ID='FAKE-BUNDLE-ID',
    APPSFLYER_WEB_DEV_KEY='FAKE-WEB-DEV-KEY',
)
class TestCaseS2Smobile(AmuseAPITestCase):
    @patch('amuse.vendor.appsflyer.s2s_mobile.generate_event_id', return_value='123')
    @patch('amuse.vendor.appsflyer.s2s_mobile.send_event.delay')
    def test_send_s2s_ios(self, mock_send, mock_generate_event_id):
        device = AppsflyerDeviceFactory(appsflyer_id='afid123', idfa='abc', idfv='ghj')
        with freeze_time("2020-01-15 06:10:12"):
            _send_s2s_ios(
                device=device,
                user_id=1,
                event_name='random',
                data={
                    'ip': '123.123.1.123',
                    'currency': 'USD',
                    'price': '12.34',
                    'plan_name': 'monthly',
                },
            )
        mock_send.assert_called_once_with(
            '123',
            'https://api2.appsflyer.com/inappevent/FAKE-IOS-APP-ID',
            {
                'appsflyer_id': 'afid123',
                'customer_user_id': 1,
                'idfa': 'abc',
                'idfv': 'ghj',
                'eventName': 'random',
                'eventValue': '{"ip": "123.123.1.123", "currency": "USD", "price": "12.34", "plan_name": "monthly"}',
                'ip': '123.123.1.123',
                'eventTime': '2020-01-15 06:10:12.000',
                'eventCurrency': 'USD',
            },
            {'authentication': 'FAKE-DEV-KEY'},
        )

    @patch('amuse.vendor.appsflyer.s2s_mobile.generate_event_id', return_value='123')
    @patch('amuse.vendor.appsflyer.s2s_mobile.send_event.delay')
    def test_send_s2s_android(self, mock_send, mock_generate_event_id):
        device = AppsflyerDeviceFactory(
            appsflyer_id='afid123', aaid='aaid', oaid='oaid', imei='imei'
        )
        with freeze_time("2020-01-15 06:10:12"):
            _send_s2s_android(
                device=device,
                user_id=1,
                event_name='random',
                data={
                    'ip': '123.123.1.123',
                    'currency': 'USD',
                    'price': '12.34',
                    'plan_name': 'monthly',
                },
            )

        mock_send.assert_called_once_with(
            '123',
            'https://api2.appsflyer.com/inappevent/FAKE-ANDROID-APP-ID',
            {
                'appsflyer_id': 'afid123',
                'customer_user_id': 1,
                'advertising_id': 'aaid',
                'oaid': 'oaid',
                'imei': 'imei',
                'eventName': 'random',
                'eventValue': '{"ip": "123.123.1.123", "currency": "USD", "price": "12.34", "plan_name": "monthly"}',
                'ip': '123.123.1.123',
                'eventTime': '2020-01-15 06:10:12.000',
                'eventCurrency': 'USD',
            },
            {'authentication': 'FAKE-DEV-KEY'},
        )
