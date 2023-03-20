from unittest.mock import patch

from django.test import override_settings

from amuse.tests.test_api.base import AmuseAPITestCase
from amuse.vendor.appsflyer.request import send_request


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
class TestCaseSendRequest(AmuseAPITestCase):
    @patch('amuse.vendor.appsflyer.request.logger.info')
    @patch('amuse.vendor.appsflyer.request.session.post')
    def test_send_request(self, mock_post, mock_logger):
        mock_post.return_value = MockResponse()
        send_request(
            event_id='123',
            url='https://www.fake.url',
            body={'example': '123', 'eventName': 'test_event_name'},
            headers={'auth': '123'},
        )

        mock_post.assert_called_once_with(
            'https://www.fake.url',
            json={'example': '123', 'eventName': 'test_event_name'},
            headers={
                'auth': '123',
                'Accept-Encoding': 'application/json',
                'Content-Type': 'application/json',
            },
            timeout=5,
        )
        mock_logger.assert_called_once_with(
            'AppsFlyer: response data, event_id: "123", event_name: "test_event_name", data: "OK"'
        )

    @patch('amuse.vendor.appsflyer.request.logger.error')
    @patch('amuse.vendor.appsflyer.request.logger.info')
    @patch('amuse.vendor.appsflyer.request.session.post')
    def test_send_request_failed_with_wrong_status(
        self, mock_post, mock_logger_info, mock_logger_error
    ):
        mock_post.return_value = MockResponse(status=400, message='Oh no')
        with self.assertRaises(Exception):
            send_request(
                event_id='123',
                url='https://www.fake.url',
                body={'example': '123'},
                headers={'auth': '123'},
            )

        mock_post.assert_called_once_with(
            'https://www.fake.url',
            json={'example': '123'},
            headers={
                'auth': '123',
                'Accept-Encoding': 'application/json',
                'Content-Type': 'application/json',
            },
            timeout=5,
        )

        self.assertEqual(0, mock_logger_info.call_count)
        self.assertEqual(0, mock_logger_error.call_count)
