from django.test import TestCase, override_settings
from unittest import mock
from releases.tests.factories import SongFileUploadFactory
from simple_history.manager import HistoryManager
from releases.models import SongFileUpload


class SongFileUploadTestCase(TestCase):
    @override_settings(AWS_REGION='mock-aws-region')
    @mock.patch('transcoder.Transcoder.encode', return_value='12415125')
    def test_songfileupload_history(self, transcode_mock):
        """SongFileUpload model history is enabled."""
        songfileupload = SongFileUpload()
        self.assertTrue(isinstance(songfileupload.history, HistoryManager))
        self.assertEqual(songfileupload.history.count(), 0)

        songfileupload = SongFileUploadFactory()
        self.assertEqual(songfileupload.history.count(), 2)
        self.assertEqual(songfileupload.history.all()[0].transcode_id, '12415125')
