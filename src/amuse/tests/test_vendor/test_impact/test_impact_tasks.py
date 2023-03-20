from unittest import mock

from django.test import TestCase

from amuse.vendor.impact import tasks


class SendEventTestCase(TestCase):
    def setUp(self) -> None:
        self.event_id = '123'
        self.params = {'example': '123', 'eventName': 'test_event'}

    @mock.patch('amuse.vendor.impact.tasks.logger.info')
    @mock.patch('amuse.vendor.impact.tasks.send_request')
    def test_send_event_success(self, mock_send_request, mock_logger):
        return_value = tasks.send_impact_event(
            event_id=self.event_id, params=self.params
        )

        mock_send_request.assert_called_once_with(self.event_id, self.params)
        mock_logger.assert_called_once_with(
            f'Impact: sending new request, event_id: "123", params: {str(self.params)}'
        )

    @mock.patch('amuse.vendor.impact.tasks.logger.warning')
    @mock.patch('amuse.vendor.impact.tasks.logger.info')
    @mock.patch('amuse.vendor.impact.tasks.send_impact_event.retry')
    @mock.patch('amuse.vendor.impact.tasks.send_request')
    def test_send_event_failed_with_exception(
        self, mock_send_request, mock_retry, mock_logger_info, mock_logger_warning
    ):
        mock_send_request.side_effect = error = Exception('Impact 400 error')
        mock_send_request.return_value = ''

        return_value = tasks.send_impact_event(
            event_id=self.event_id, params=self.params
        )

        mock_send_request.assert_called_once_with(self.event_id, self.params)

        mock_retry.assert_called_once()

        mock_logger_info.assert_called_once_with(
            f'Impact: sending new request, event_id: "123", params: {str(self.params)}'
        )

        mock_logger_warning.assert_called_once_with(
            f'Impact: error sending request, event_id: "123", retry: 0, exception: {mock_send_request.side_effect}'
        )
