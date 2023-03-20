from django.test import TestCase
from unittest import mock

from amuse.vendor.appsflyer import tasks


class SendEventTestCase(TestCase):
    def setUp(self) -> None:
        self.event_id = '123'
        self.url = 'http://example.com/xyz'
        self.data = {'example': '123', 'eventName': 'test_event'}
        self.headers = {'authorization': 'B 123'}

    @mock.patch('amuse.vendor.appsflyer.tasks.logger.info')
    @mock.patch('amuse.vendor.appsflyer.tasks.send_request')
    def test_send_event_success(self, mock_send_request, mock_logger):
        return_value = tasks.send_event(
            event_id=self.event_id, url=self.url, data=self.data, headers=self.headers
        )

        mock_send_request.assert_called_once_with(
            self.event_id, self.url, self.data, self.headers
        )
        mock_logger.assert_called_once_with(
            'AppsFlyer: sending new request, event_id: "123", event_name: "test_event"'
        )

    @mock.patch('amuse.vendor.appsflyer.tasks.logger.error')
    @mock.patch('amuse.vendor.appsflyer.tasks.logger.info')
    @mock.patch('amuse.vendor.appsflyer.tasks.send_event.retry')
    @mock.patch('amuse.vendor.appsflyer.tasks.send_request')
    def test_send_event_failed_with_exception(
        self, mock_send_request, mock_retry, mock_logger_info, mock_logger_exception
    ):
        mock_send_request.side_effect = error = Exception('Appsflyer 400 error')
        mock_send_request.return_value = ''

        return_value = tasks.send_event(
            event_id=self.event_id, url=self.url, data=self.data, headers=self.headers
        )

        mock_send_request.assert_called_once_with(
            self.event_id, self.url, self.data, self.headers
        )

        mock_retry.assert_called_once()

        mock_logger_info.assert_called_once_with(
            'AppsFlyer: sending new request, event_id: "123", event_name: "test_event"'
        )

        mock_logger_exception.assert_called_once_with(
            f'AppsFlyer: error sending request, event_id: "123", event_name: "test_event", exception: {mock_send_request.side_effect}'
        )
