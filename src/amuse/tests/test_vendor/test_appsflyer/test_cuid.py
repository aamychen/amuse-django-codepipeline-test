from unittest.mock import patch

from django.test import override_settings
from freezegun import freeze_time

from amuse.tests.test_api.base import AmuseAPITestCase
from amuse.vendor.appsflyer.cuid import send_set_cuid


class MockResponse:
    def __init__(self, message='OK', status=200):
        self.text = message
        self.message = message
        self.status_code = status

    def json(self):
        return {'message': self.message, 'status': self.status_code}


@override_settings(
    APPSFLYER_ENABLED=True,
    APPSFLYER_IOS_APP_ID='FAKE-IOS-APP-ID',
    APPSFLYER_ANDROID_APP_ID='FAKE-ANDROID-APP-ID',
    APPSFLYER_DEV_KEY='FAKE-DEV-KEY',
    APPSFLYER_BRAND_BUNDLE_ID='FAKE-BUNDLE-ID',
    APPSFLYER_WEB_DEV_KEY='FAKE-WEB-DEV-KEY',
)
class TestCaseCuid(AmuseAPITestCase):
    @patch('amuse.vendor.appsflyer.request.logger.info')
    @patch('amuse.vendor.appsflyer.request.session.post')
    def test_send_set_cuid(self, mock_post, mock_logger):
        mock_post.return_value = MockResponse()
        with freeze_time("2020-01-15 06:10:12"):
            send_set_cuid(user_id=123, af_user_id='abc')

        mock_post.assert_called_once_with(
            'https://webs2s.appsflyer.com/v1/FAKE-BUNDLE-ID/setcuid',
            json={
                'customerUserId': '123',
                'afUserId': 'abc',
                'webDevKey': 'FAKE-WEB-DEV-KEY',
            },
            headers={
                'Accept-Encoding': 'application/json',
                'Content-Type': 'application/json',
            },
            timeout=5,
        )
        mock_logger.assert_called_once()

    @override_settings(APPSFLYER_ENABLED=False)
    @patch('amuse.vendor.appsflyer.request.logger.info')
    @patch('amuse.vendor.appsflyer.request.session.post')
    def test_send_set_cuid_not_send(self, mock_post, mock_logger):
        send_set_cuid(user_id=123, af_user_id='abc')

        self.assertEqual(0, mock_logger.call_count)
        self.assertEqual(0, mock_post.call_count)
