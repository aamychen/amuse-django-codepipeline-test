from unittest import mock

from django.test import TestCase

from amuse.vendor.segment import tasks


class SendEventTestCase(TestCase):
    def setUp(self) -> None:
        self.user_id = 123
        self.event_name = 'test_event_abc'
        self.data = {'example': '123', 'eventName': 'test_event'}
        self.context = {'client': 'test case client', 'ip': '10.0.0.202'}

    @mock.patch('amuse.vendor.segment.tasks.logger.info')
    @mock.patch('amuse.vendor.segment.tasks.track')
    def test_send_event_success(self, mock_track, mock_logger):
        tasks.send_segment_track(
            self.user_id, self.event_name, properties=self.data, context=self.context
        )

        mock_track.assert_called_once_with(
            self.user_id, self.event_name, properties=self.data, context=self.context
        )
        mock_logger.assert_called_once_with(
            f'Segment track event test_event_abc, properties={self.data}, context={self.context}'
        )

    @mock.patch('amuse.vendor.segment.tasks.logger.error')
    @mock.patch('amuse.vendor.segment.tasks.logger.info')
    @mock.patch('amuse.vendor.segment.tasks.send_segment_track.retry')
    @mock.patch('amuse.vendor.segment.tasks.track')
    def test_send_event_failed_with_exception(
        self, mock_track, mock_retry, mock_logger_info, mock_logger_exception
    ):
        mock_track.side_effect = Exception('Segment Error')
        mock_track.return_value = ''

        tasks.send_segment_track(
            self.user_id, self.event_name, properties=self.data, context=self.context
        )

        mock_track.assert_called_once_with(
            self.user_id, self.event_name, properties=self.data, context=self.context
        )

        mock_retry.assert_called_once()

        mock_logger_info.assert_called_once_with(
            f'Segment track event test_event_abc, properties={self.data}, context={self.context}'
        )

        mock_logger_exception.assert_called_once_with(
            f'Segment track event error, event={self.event_name}, '
            f'properties={self.data}, '
            f'context={self.context}',
            f'exception={Exception("Segment Error")}',
        )


class SendIdentifyTestCase(TestCase):
    def setUp(self) -> None:
        self.user_id = 123
        self.traits = {'email': 'a@b.c', 'is_pro': 'true'}

    @mock.patch('amuse.vendor.segment.tasks.logger.info')
    @mock.patch('amuse.vendor.segment.tasks.identify')
    def test_identify_success(self, mock_identify, mock_logger):
        tasks.send_segment_identify(self.user_id, self.traits)

        mock_identify.assert_called_once_with(self.user_id, self.traits)

        mock_logger.assert_called_once_with(f'Segment identify, traits={self.traits}')

    @mock.patch('amuse.vendor.segment.tasks.logger.error')
    @mock.patch('amuse.vendor.segment.tasks.logger.info')
    @mock.patch('amuse.vendor.segment.tasks.send_segment_identify.retry')
    @mock.patch('amuse.vendor.segment.tasks.identify')
    def test_identify_failed_with_exception(
        self, mock_identify, mock_retry, mock_logger_info, mock_logger_exception
    ):
        mock_identify.side_effect = Exception('Segment Identify Error')
        mock_identify.return_value = ''

        tasks.send_segment_identify(self.user_id, self.traits)
        mock_identify.assert_called_once_with(self.user_id, self.traits)

        mock_retry.assert_called_once()

        mock_logger_info.assert_called_once_with(
            f'Segment identify, traits={self.traits}'
        )

        mock_logger_exception.assert_called_once_with(
            f'Segment identify error, traits={self.traits}, exception={Exception("Segment Identify Error")}'
        )
