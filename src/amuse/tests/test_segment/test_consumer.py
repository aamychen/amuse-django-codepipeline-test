from django.test import TestCase
from unittest import mock
from amuse.tests.test_segment.mock_response import MockResponse
from amuse.vendor.segment.consumer import Consumer
from requests import Session
from queue import Queue


class TestConsumer(TestCase):
    def test_next(self):
        q = Queue()
        consumer = Consumer(q, '')
        q.put(1)
        next = consumer.next()
        self.assertEqual(next, [1])

    def test_next_limit(self):
        q = Queue()
        upload_size = 50
        consumer = Consumer(q, '', upload_size)
        for i in range(10000):
            q.put(i)
        next = consumer.next()
        self.assertEqual(next, list(range(upload_size)))

    @mock.patch.object(Session, 'post', return_value=MockResponse(status_code=200))
    def test_upload(self, mockdata):
        q = Queue()
        consumer = Consumer(q, 'testsecret')
        track = {'type': 'track', 'event': 'python event', 'userId': 'userId'}
        q.put(track)
        success = consumer.upload()
        self.assertTrue(success)

    @mock.patch.object(Session, 'post', return_value=MockResponse(status_code=200))
    def test_request(self, mockdata):
        consumer = Consumer(None, 'testsecret')
        track = {'type': 'track', 'event': 'python event', 'userId': 'userId'}
        consumer.request([track])

    def test_pause(self):
        consumer = Consumer(None, 'testsecret')
        consumer.pause()
        self.assertFalse(consumer.running)
