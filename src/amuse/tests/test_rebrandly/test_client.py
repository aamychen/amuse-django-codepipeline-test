from django.test import TestCase
from unittest import mock
from requests import Response
import responses
from django.test import override_settings
from amuse.vendor.rebrandly.client import Rebrandly, RebrandlyException

REBRANDLY_MOCK_SETTINGS = {
    'REBRANDLY_API_KEY': 'api-key',
    'REBRANDLY_DOMAIN': 'rebrand.ly',
    'REBRANDLY_ENABLED': True,
    'REBRANDLY_APP_IDS': '123,456',
}

REBRANDLY_API_URL = 'https://api.rebrandly.com/v1/links'


@override_settings(**REBRANDLY_MOCK_SETTINGS)
class TestClient(TestCase):
    def setUp(self):
        self.client = Rebrandly()

    @mock.patch('requests.post')
    def test_original_link_returned_on_api_fail(self, post_mock):
        long_url = 'https://www.mockurl.com/'

        response = Response()
        response.status_code = 405
        response.reason = 'fake news'
        response._content = b'fake news'
        post_mock.return_value = response

        generated_url = self.client.generate_link(long_url)
        self.assertEqual(generated_url, long_url)

    @override_settings(REBRANDLY_ENABLED=False)
    def test_original_link_returned_on_client_disabled(self):
        long_url = 'https://www.mockurl.com/'
        generated_url = self.client.generate_link(long_url)
        self.assertEqual(generated_url, long_url)

    @responses.activate
    @mock.patch.object(Rebrandly, 'link_app')
    @mock.patch('requests.post')
    def test_generate_link(self, post_mock, link_app_mock):
        original_url = "https://original.invalid"
        short_url = 'https://short.invalid'

        response = Response()
        response.status_code = 200
        response.reason = 'fake news'
        response._content = b'{"id": "urlid", "shortUrl": "https://short.invalid"}'
        post_mock.return_value = response

        return_url = self.client.generate_link(original_url)
        self.assertEqual(2, link_app_mock.call_count)
        self.assertEqual(short_url, return_url)

        post_mock.assert_called_once_with(
            REBRANDLY_API_URL,
            json={
                'destination': original_url,
                'domain': {'fullName': REBRANDLY_MOCK_SETTINGS['REBRANDLY_DOMAIN']},
            },
            headers={
                'Content-Type': 'application/json',
                'apikey': REBRANDLY_MOCK_SETTINGS['REBRANDLY_API_KEY'],
            },
        )

    @responses.activate
    @mock.patch.object(Rebrandly, 'link_app')
    @mock.patch('requests.post')
    def test_generate_link_successful_without_ids(self, post_mock, link_app_mock):
        original_url = "https://original.invalid"
        short_url = 'https://short.invalid'

        response = Response()
        response.status_code = 200
        response.reason = 'fake news'
        response._content = b'{"id": "urlid", "shortUrl": "https://short.invalid"}'
        post_mock.return_value = response
        self.client.app_ids = []

        return_url = self.client.generate_link(original_url)
        self.assertEqual(0, link_app_mock.call_count)
        self.assertEqual(short_url, return_url)

        post_mock.assert_called_once_with(
            REBRANDLY_API_URL,
            json={
                'destination': original_url,
                'domain': {'fullName': REBRANDLY_MOCK_SETTINGS['REBRANDLY_DOMAIN']},
            },
            headers={
                'Content-Type': 'application/json',
                'apikey': REBRANDLY_MOCK_SETTINGS['REBRANDLY_API_KEY'],
            },
        )

    @responses.activate
    @override_settings(REBRANDLY_ENABLED=False)
    @mock.patch('requests.post')
    def test_generate_links_original_url_returned_on_client_disabled(self, get_mock):
        response = Response()
        get_mock.return_value = response

        url = self.client.generate_link("https://original.invalid")

        self.assertEqual(0, get_mock.call_count)
        self.assertEqual("https://original.invalid", url)

    @responses.activate
    @mock.patch('requests.post')
    def test_generate_links_empty_array_returned_on_api_fail(self, post_mock):
        response = Response()
        response.status_code = 500
        post_mock.side_effect = error = Exception()
        post_mock.return_value = response

        url = self.client.generate_link("https://original.invalid")

        self.assertEqual(1, post_mock.call_count)
        self.assertEqual("https://original.invalid", url)

    @responses.activate
    @mock.patch('amuse.vendor.rebrandly.client.logger', autospec=True)
    @mock.patch('requests.post')
    def test_link_app_failed(self, post_mock, logger_mock):
        response = Response()
        response.status_code = 500
        post_mock.return_value = response

        link_id = "LINKID"
        app_id = "APPID"
        self.client.link_app("https://original.invalid", link_id, app_id)

        logger_mock.exception.assert_called_once()
