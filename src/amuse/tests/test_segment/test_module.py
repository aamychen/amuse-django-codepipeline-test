from requests import Session
from amuse.vendor import segment
from django.test import TestCase
from unittest import mock
from amuse.tests.test_segment.mock_response import MockResponse


class TestModule(TestCase):
    def failed(self):
        self.failed = True

    def setUp(self):
        self.failed = False
        segment.write_key = 'testsecret'
        segment.on_error = self.failed

    def test_no_write_key(self):
        segment.write_key = None
        self.assertRaises(Exception, segment.track)

    def test_no_host(self):
        segment.host = None
        self.assertRaises(Exception, segment.track)

    @mock.patch.object(Session, 'post', return_value=MockResponse(status_code=200))
    def test_track(self, mockdata):
        segment.track('userId', 'python module event')
        segment.flush()

    @mock.patch.object(Session, 'post', return_value=MockResponse(status_code=200))
    def test_identify(self, mockdata):
        segment.identify('userId', {'email': 'user@email.com'})
        segment.flush()

    def test_flush(self):
        segment.flush()
