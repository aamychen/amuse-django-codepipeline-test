from unittest.mock import patch

from django.test import override_settings, TestCase

from amuse.tests.test_api.base import AmuseAPITestCase
from amuse.vendor.appsflyer.s2s import send_s2s
from amuse.vendor.appsflyer.s2s_mobile import _get_event_value
from users.tests.factories import AppsflyerDeviceFactory


@override_settings(
    APPSFLYER_ENABLED=True,
    APPSFLYER_IOS_APP_ID='FAKE-IOS-APP-ID',
    APPSFLYER_ANDROID_APP_ID='FAKE-ANDROID-APP-ID',
    APPSFLYER_DEV_KEY='FAKE-DEV-KEY',
    APPSFLYER_BRAND_BUNDLE_ID='FAKE-BUNDLE-ID',
    APPSFLYER_WEB_DEV_KEY='FAKE-WEB-DEV-KEY',
)
class TestCaseGetEvent(AmuseAPITestCase):
    def test_get_event(self):
        self.assertEqual('', _get_event_value({}))

        self.assertEqual('', _get_event_value(None))

        actual = _get_event_value(
            {'currency': 'USD', 'price': 10.20, 'plan_name': 'monthly'}
        )
        expected = '{"currency": "USD", "price": 10.2, "plan_name": "monthly"}'
        self.assertEqual(expected, actual)


class TestCaseTestS2SSend(TestCase):
    def setUp(self):
        self.user_id = 8
        self.event_name = 'event'
        self.currency_code = 'USD'
        self.price = str(12.34)
        self.plan_name = 'monthly'
        self.ip = '127.0.0.2'

    @override_settings(APPSFLYER_ENABLED=True)
    @patch('amuse.vendor.appsflyer.s2s._send_s2s_web')
    def test_send_s2s_web(self, mock_send):
        device = AppsflyerDeviceFactory(appsflyer_id='123')
        send_s2s(
            device,
            self.user_id,
            self.event_name,
            {
                'currency': self.currency_code,
                'price': self.price,
                'plan_name': self.plan_name,
                'ip': self.ip,
            },
        )
        mock_send.assert_called_once_with(
            device,
            self.user_id,
            self.event_name,
            {
                'currency': self.currency_code,
                'price': self.price,
                'plan_name': self.plan_name,
                'ip': self.ip,
            },
        )

    @override_settings(APPSFLYER_ENABLED=True)
    @patch('amuse.vendor.appsflyer.s2s._send_s2s_ios')
    def test_send_s2s_ios(self, mock_send):
        device = AppsflyerDeviceFactory(appsflyer_id='123', idfa='idfa')
        send_s2s(
            device,
            self.user_id,
            self.event_name,
            {
                'currency': self.currency_code,
                'price': self.price,
                'plan_name': self.plan_name,
                'ip': self.ip,
            },
        )
        mock_send.assert_called_once_with(
            device,
            self.user_id,
            self.event_name,
            {
                'currency': self.currency_code,
                'price': self.price,
                'plan_name': self.plan_name,
                'ip': self.ip,
            },
        )

    @override_settings(APPSFLYER_ENABLED=True)
    @patch('amuse.vendor.appsflyer.s2s._send_s2s_android')
    def test_send_s2s_android(self, mock_send):
        device = AppsflyerDeviceFactory(appsflyer_id='123', aaid='aaid')
        send_s2s(
            device,
            self.user_id,
            self.event_name,
            {
                'currency': self.currency_code,
                'price': self.price,
                'plan_name': self.plan_name,
                'ip': self.ip,
            },
        )
        mock_send.assert_called_once_with(
            device,
            self.user_id,
            self.event_name,
            {
                'currency': self.currency_code,
                'price': self.price,
                'plan_name': self.plan_name,
                'ip': self.ip,
            },
        )

    @override_settings(APPSFLYER_ENABLED=True)
    @patch('amuse.vendor.appsflyer.s2s._send_s2s_ios')
    @patch('amuse.vendor.appsflyer.s2s._send_s2s_android')
    @patch('amuse.vendor.appsflyer.s2s._send_s2s_web')
    def test_device_is_none(self, mock_web, mock_android, mock_ios):
        send_s2s(None, self.user_id, self.event_name, {})
        self.assertEqual(0, mock_web.call_count)
        self.assertEqual(0, mock_android.call_count)
        self.assertEqual(0, mock_ios.call_count)

    @override_settings(APPSFLYER_ENABLED=False)
    @patch('amuse.vendor.appsflyer.s2s._send_s2s_ios')
    @patch('amuse.vendor.appsflyer.s2s._send_s2s_android')
    @patch('amuse.vendor.appsflyer.s2s._send_s2s_web')
    def test_device_do_not_send_id_appsflyer_disabled(
        self, mock_web, mock_android, mock_ios
    ):
        send_s2s(None, self.user_id, self.event_name, {})
        self.assertEqual(0, mock_web.call_count)
        self.assertEqual(0, mock_android.call_count)
        self.assertEqual(0, mock_ios.call_count)
