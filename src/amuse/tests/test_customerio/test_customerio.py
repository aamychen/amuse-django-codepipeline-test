import json
from django.test import TestCase
from unittest import mock
from requests import Session

from amuse.vendor.customerio import CustomerIO, CustomerIOException


class MockResponse:
    def __init__(self, status_code):
        self.status_code = status_code
        self.content = "Mock data"
        self.text = "123"


class TestCustomerIO(TestCase):
    """Starts server which the client connects to in the following tests"""

    def setUp(self):
        self.cio = CustomerIO(
            site_id='siteid', api_key='apikey', host="host", port=3210, retries=5
        )

        # do not verify the ssl certificate as it is self signed
        # should only be done for tests
        self.cio.http.verify = False

    def _check_request(self, resp, rq, *args, **kwargs):
        request = resp.request
        body = (
            request.body.decode('utf-8')
            if isinstance(request.body, bytes)
            else request.body
        )
        self.assertEqual(request.method, rq['method'])
        self.assertEqual(json.loads(body), rq['body'])
        self.assertEqual(request.headers['Authorization'], rq['authorization'])
        self.assertEqual(request.headers['Content-Type'], rq['content_type'])
        self.assertEqual(
            int(request.headers['Content-Length']), len(json.dumps(rq['body']))
        )
        self.assertTrue(
            request.url.endswith(rq['url_suffix']),
            'url: {} expected suffix: {}'.format(request.url, rq['url_suffix']),
        )

    @mock.patch.object(Session, 'send', return_value=MockResponse(status_code=200))
    def test_identify_call(self, mockdata):
        self.cio.identify(id=1, name="hamo", email="hamo@example.com")

        with self.assertRaises(TypeError):
            self.cio.identify(random_attr="some_value")

    @mock.patch.object(Session, 'send', return_value=MockResponse(status_code=200))
    def test_track_call(self, mockdata):
        self.cio.track(customer_id=1, name="send_email", email="john@example.com")

        with self.assertRaises(TypeError):
            self.cio.track(random_attr="some_value")

    @mock.patch.object(Session, 'send', return_value=MockResponse(status_code=200))
    def test_pageview_call(self, mockdata):
        self.cio.pageview(customer_id=1, page='product_1', referer='category_1')

        with self.assertRaises(TypeError):
            self.cio.pageview(random_attr="some_value")

    @mock.patch.object(Session, 'send', return_value=MockResponse(status_code=200))
    def test_delete_call(self, mockdata):
        self.cio.delete(customer_id=1)

        with self.assertRaises(TypeError):
            self.cio.delete(random_attr="some_value")

    @mock.patch.object(Session, 'send', return_value=MockResponse(status_code=200))
    def test_backfill_call(self, mockdata):
        self.cio.backfill(
            customer_id=1, name='signup', timestamp=1234567890, email="john@example.com"
        )

        with self.assertRaises(TypeError):
            self.cio.backfill(random_attr="some_value")

    def test_base_url(self):
        test_cases = [
            # host, port, prefix, result
            (None, None, None, 'https://track.customer.io/api/v1'),
            (None, None, 'v2', 'https://track.customer.io/v2'),
            (None, None, '/v2/', 'https://track.customer.io/v2'),
            ('sub.domain.com', 1337, '/v2/', 'https://sub.domain.com:1337/v2'),
            ('/sub.domain.com/', 1337, '/v2/', 'https://sub.domain.com:1337/v2'),
            ('http://sub.domain.com/', 1337, '/v2/', 'https://sub.domain.com:1337/v2'),
        ]

        for host, port, prefix, result in test_cases:
            cio = CustomerIO(host=host, port=port, url_prefix=prefix)
            self.assertEqual(cio.base_url, result)

    @mock.patch.object(Session, 'send', return_value=MockResponse(status_code=200))
    def test_device_call(self, mockdata):
        self.cio.add_device(customer_id=1, device_id="device_1", platform="ios")
        with self.assertRaises(TypeError):
            self.cio.add_device(random_attr="some_value")

    @mock.patch.object(Session, 'send', return_value=MockResponse(status_code=200))
    def test_device_call_last_used(self, mockdata):
        self.cio.add_device(
            customer_id=1,
            device_id="device_2",
            platform="android",
            last_used=1234567890,
        )

    @mock.patch.object(Session, 'send', return_value=MockResponse(status_code=200))
    def test_device_call_valid_platform(self, mockdata):
        with self.assertRaises(CustomerIOException):
            self.cio.add_device(customer_id=1, device_id="device_3", platform=None)

    @mock.patch.object(Session, 'send', return_value=MockResponse(status_code=200))
    def test_device_call_has_customer_id(self, mockdata):
        with self.assertRaises(CustomerIOException):
            self.cio.add_device(customer_id="", device_id="device_4", platform="ios")

    @mock.patch.object(Session, 'send', return_value=MockResponse(status_code=200))
    def test_device_call_has_device_id(self, mockdata):
        with self.assertRaises(CustomerIOException):
            self.cio.add_device(customer_id=1, device_id="", platform="ios")

    @mock.patch.object(Session, 'send', return_value=MockResponse(status_code=200))
    def test_device_delete_call(self, mockdata):
        self.cio.delete_device(customer_id=1, device_id="device_1")
        with self.assertRaises(TypeError):
            self.cio.delete_device(random_attr="some_value")

    @mock.patch.object(Session, 'send', return_value=MockResponse(status_code=200))
    def test_suppress_call(self, mockdata):
        self.cio.suppress(customer_id=1)

        with self.assertRaises(CustomerIOException):
            self.cio.suppress(None)

    @mock.patch.object(Session, 'send', return_value=MockResponse(status_code=200))
    def test_unsuppress_call(self, mockdata):
        self.cio.unsuppress(customer_id=1)

        with self.assertRaises(CustomerIOException):
            self.cio.unsuppress(None)

    @mock.patch.object(Session, 'send', return_value=MockResponse(status_code=200))
    def test_add_to_segment_call(self, mockdata):
        self.cio.add_to_segment(segment_id=1, customer_ids=[1, 2, 3])

        with self.assertRaises(CustomerIOException):
            self.cio.add_to_segment(None, None)

        with self.assertRaises(CustomerIOException):
            self.cio.add_to_segment(segment_id=1, customer_ids=False)

    @mock.patch.object(Session, 'send', return_value=MockResponse(status_code=200))
    def test_remove_from_segment_call(self, mockdata):
        self.cio.remove_from_segment(segment_id=1, customer_ids=[1, 2, 3])

        with self.assertRaises(CustomerIOException):
            self.cio.remove_from_segment(None, None)

        with self.assertRaises(CustomerIOException):
            self.cio.add_to_segment(segment_id=1, customer_ids=False)
