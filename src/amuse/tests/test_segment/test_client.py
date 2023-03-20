from datetime import date, datetime
import six
from django.test import TestCase
from unittest import mock

from amuse.vendor.segment.version import VERSION
from amuse.vendor.segment.client import Client
from amuse.tests.test_segment.mock_response import MockResponse
from requests import Session


class TestClient(TestCase):
    def fail(self, e, batch):
        """Mark the failure handler"""
        self.failed = True

    def setUp(self):
        self.failed = False
        self.client = Client('testsecret', on_error=self.fail)

    def test_no_write_key_sets_send_to_false(self):
        client = Client()
        self.assertFalse(client.send)

    def test_empty_flush(self):
        self.client.flush()

    @mock.patch.object(Session, 'post', return_value=MockResponse(status_code=200))
    def test_basic_track(self, mockadata):
        client = self.client
        success, msg = client.track('userId', 'python test event')
        client.flush()
        self.assertTrue(success)
        self.assertFalse(self.failed)

        self.assertEqual(msg['event'], 'python test event')
        self.assertTrue(isinstance(msg['timestamp'], str))
        self.assertTrue(isinstance(msg['messageId'], str))
        self.assertEqual(msg['userId'], 'userId')
        self.assertEqual(msg['properties'], {})
        self.assertEqual(msg['type'], 'track')

    @mock.patch.object(Session, 'post', return_value=MockResponse(status_code=200))
    def test_stringifies_user_id(self, mockdata):
        # A large number that loses precision in node:
        # node -e "console.log(157963456373623802 + 1)" > 157963456373623800
        client = self.client
        success, msg = client.track(
            user_id=157963456373623802, event='python test event'
        )
        client.flush()
        self.assertTrue(success)
        self.assertFalse(self.failed)

        self.assertEqual(msg['userId'], '157963456373623802')
        self.assertEqual(msg['anonymousId'], None)

    @mock.patch.object(Session, 'post', return_value=MockResponse(status_code=200))
    def test_stringifies_anonymous_id(self, mockdata):
        # A large number that loses precision in node:
        # node -e "console.log(157963456373623803 + 1)" > 157963456373623800
        client = self.client
        success, msg = client.track(
            anonymous_id=157963456373623803, event='python test event'
        )
        client.flush()
        self.assertTrue(success)
        self.assertFalse(self.failed)

        self.assertEqual(msg['userId'], None)
        self.assertEqual(msg['anonymousId'], '157963456373623803')

    @mock.patch.object(Session, 'post', return_value=MockResponse(status_code=200))
    def test_advanced_track(self, mockdata):
        client = self.client
        success, msg = client.track(
            'userId',
            'python test event',
            {'property': 'value'},
            {'ip': '192.168.0.1'},
            datetime(2014, 9, 3),
            'anonymousId',
            {'Amplitude': True},
        )

        self.assertTrue(success)

        self.assertEqual(msg['timestamp'], '2014-09-03T00:00:00+00:00')
        self.assertEqual(msg['properties'], {'property': 'value'})
        self.assertEqual(msg['integrations'], {'Amplitude': True})
        self.assertEqual(msg['context']['ip'], '192.168.0.1')
        self.assertEqual(msg['event'], 'python test event')
        self.assertEqual(msg['anonymousId'], 'anonymousId')
        self.assertEqual(
            msg['context']['library'],
            {'name': 'analytics-python-amuse', 'version': VERSION},
        )
        self.assertTrue(isinstance(msg['messageId'], str))
        self.assertEqual(msg['userId'], 'userId')
        self.assertEqual(msg['type'], 'track')

    @mock.patch.object(Session, 'post', return_value=MockResponse(status_code=200))
    def test_basic_identify(self, mockdata):
        client = self.client
        success, msg = client.identify('userId', {'trait': 'value'})
        client.flush()
        self.assertTrue(success)
        self.assertFalse(self.failed)

        self.assertEqual(msg['traits'], {'trait': 'value'})
        self.assertTrue(isinstance(msg['timestamp'], str))
        self.assertTrue(isinstance(msg['messageId'], str))
        self.assertEqual(msg['userId'], 'userId')
        self.assertEqual(msg['type'], 'identify')

    @mock.patch.object(Session, 'post', return_value=MockResponse(status_code=200))
    def test_advanced_identify(self, mockdata):
        client = self.client
        success, msg = client.identify(
            'userId',
            {'trait': 'value'},
            {'ip': '192.168.0.1'},
            datetime(2014, 9, 3),
            'anonymousId',
            {'Amplitude': True},
        )

        self.assertTrue(success)

        self.assertEqual(msg['timestamp'], '2014-09-03T00:00:00+00:00')
        self.assertEqual(msg['integrations'], {'Amplitude': True})
        self.assertEqual(msg['context']['ip'], '192.168.0.1')
        self.assertEqual(msg['traits'], {'trait': 'value'})
        self.assertEqual(msg['anonymousId'], 'anonymousId')
        self.assertEqual(
            msg['context']['library'],
            {'name': 'analytics-python-amuse', 'version': VERSION},
        )
        self.assertTrue(isinstance(msg['timestamp'], str))
        self.assertTrue(isinstance(msg['messageId'], str))
        self.assertEqual(msg['userId'], 'userId')
        self.assertEqual(msg['type'], 'identify')

    @mock.patch.object(Session, 'post', return_value=MockResponse(status_code=200))
    def test_flush(self, mockdata):
        client = self.client
        # set up the consumer with more requests than a single batch will allow
        for i in range(1000):
            success, msg = client.identify('userId', {'trait': 'value'})
        # We can't reliably assert that the queue is non-empty here; that's
        # a race condition. We do our best to load it up though.
        client.flush()
        # Make sure that the client queue is empty after flushing
        self.assertTrue(client.queue.empty())

    @mock.patch.object(Session, 'post', return_value=MockResponse(status_code=200))
    def test_success_on_invalid_write_key(self, mockdata):
        client = Client('bad_key', on_error=self.fail)
        client.track('userId', 'event')
        client.flush()
        self.assertFalse(self.failed)

    def test_unicode(self):
        Client(six.u('unicode_key'))

    @mock.patch.object(Session, 'post', return_value=MockResponse(status_code=200))
    def test_numeric_user_id(self, mockdata):
        self.client.track(1234, 'python event')
        self.client.flush()
        self.assertFalse(self.failed)

    def test_debug(self):
        Client('bad_key', debug=True)

    @mock.patch.object(Session, 'post', return_value=MockResponse(status_code=200))
    def test_identify_with_date_object(self, mockdata):
        client = self.client
        success, msg = client.identify('userId', {'birthdate': date(1981, 2, 2)})
        client.flush()
        self.assertTrue(success)
        self.assertFalse(self.failed)

        self.assertEqual(msg['traits'], {'birthdate': date(1981, 2, 2)})
