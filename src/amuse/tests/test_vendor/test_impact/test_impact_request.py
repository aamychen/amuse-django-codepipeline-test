from unittest.mock import patch

from django.test import override_settings

from amuse.tests.test_api.base import AmuseAPITestCase
from amuse.vendor.impact.request import send_request


class MockResponse:
    def __init__(self, message='OK', status=200):
        self.text = message
        self.message = message
        self.status_code = status

    def json(self):
        return {'message': self.message, 'status': self.status_code}


@override_settings(
    IMPACT_ENABLED=True, IMPACT_SID='FAKE-SID', IMPACT_PASSWORD='FAKE-PASSWORD'
)
class TestCaseSendRequest(AmuseAPITestCase):
    @patch('amuse.vendor.impact.request.logger.info')
    @patch('amuse.vendor.impact.request.requests.post')
    def test_send_request(self, mock_post, mock_logger):
        mock_post.return_value = MockResponse()
        send_request(event_id='123', params={'example': '123'})

        mock_post.assert_called_once()
        mock_logger.assert_called_once_with(
            'Impact: response data, event_id: "123", data: "OK"'
        )

    @patch('amuse.vendor.impact.request.logger.error')
    @patch('amuse.vendor.impact.request.logger.info')
    @patch('amuse.vendor.impact.request.requests.post')
    def test_send_request_failed_with_wrong_status(
        self, mock_post, mock_logger_info, mock_logger_error
    ):
        mock_post.return_value = MockResponse(status=400, message='Oh no')
        with self.assertRaises(Exception):
            send_request(event_id='123', params={'example': '123'})
        mock_post.assert_called_once()

        self.assertEqual(0, mock_logger_info.call_count)
        self.assertEqual(0, mock_logger_error.call_count)
