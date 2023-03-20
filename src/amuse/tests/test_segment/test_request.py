from datetime import datetime, date
import json
from requests import Session
from django.test import TestCase
from unittest import mock
from amuse.vendor.segment.request import post, DatetimeSerializer
from amuse.tests.test_segment.mock_response import MockResponse


class TestRequests(TestCase):
    @mock.patch.object(Session, 'post', return_value=MockResponse(200))
    def test_valid_request(self, mockadata):
        res = post(
            'testsecret',
            batch=[{'userId': 'userId', 'event': 'python event', 'type': 'track'}],
        )

        self.assertEqual(res.status_code, 200)

    @mock.patch.object(Session, 'post', return_value=MockResponse(200))
    def test_invalid_request_error(self, mockadata):
        self.assertRaises(
            Exception, post, 'testsecret', 'https://api.segment.io', '[{]'
        )

    @mock.patch.object(Session, 'post', return_value=ValueError())
    def test_invalid_host(self, mockadata):
        self.assertRaises(Exception, post, 'testsecret', 'api.segment.io/', batch=[])

    def test_datetime_serialization(self):
        data = {'created': datetime(2012, 3, 4, 5, 6, 7, 891011)}
        result = json.dumps(data, cls=DatetimeSerializer)
        self.assertEqual(result, '{"created": "2012-03-04T05:06:07.891011"}')

    def test_date_serialization(self):
        today = date.today()
        data = {'created': today}
        result = json.dumps(data, cls=DatetimeSerializer)
        expected = '{"created": "%s"}' % today.isoformat()
        self.assertEqual(result, expected)
