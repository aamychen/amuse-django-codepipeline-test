import responses
import requests
import json
from unittest.mock import patch
from django.test import TestCase, override_settings
from django.conf import settings
from amuse.vendor.google.captcha import verify, is_human


@override_settings(GOOGLE_CAPTCHA_ENABLED=True)
class TestGoogleCaptchaVerify(TestCase):
    @responses.activate
    def test_get_verify_results_success(self):
        response = {
            "success": True,
            "challenge_ts": "2022-12-24T12:19:49Z",
            "hostname": "127.0.0.1",
            "score": 0.9,
            "action": "test",
        }
        responses.add(
            responses.POST,
            settings.GOOGLE_CAPTCHA_ENDPOINT,
            json.dumps(response),
            status=200,
        )
        result = verify(client_side_token="a")
        self.assertEqual(result["success"], True)
        self.assertEqual(result["score"], 0.9)

    @responses.activate
    def test_get_verify_results_wrong_return_status(self):
        responses.add(responses.POST, settings.GOOGLE_CAPTCHA_ENDPOINT, status=500)
        result = verify(client_side_token="a")
        self.assertEqual(result["success"], False)
        self.assertEqual(result['error-codes'][0], "invalid-response-code")

    @patch('requests.post')
    def test_request_post_exception(self, post_mock):
        post_mock.side_effect = requests.exceptions.ConnectionError()
        result = verify(client_side_token="a")
        self.assertEqual(result["success"], False)
        self.assertEqual(result['error-codes'][0], "request-exception")

    @patch('requests.post')
    def test_is_human_system_error(self, post_mock):
        post_mock.side_effect = requests.exceptions.ConnectionError()
        result = is_human(client_side_token="a")
        self.assertTrue(result)

    @override_settings(GOOGLE_CAPTCHA_ENABLED=False)
    @patch('requests.post')
    def test_captcha_disabled(self, post_mock):
        result = is_human(client_side_token="a")
        self.assertTrue(result)
        self.assertEqual(post_mock.call_count, 0)

    @responses.activate
    def test_is_human_v3_low_score(self):
        response = {
            "success": True,
            "challenge_ts": "2022-12-24T12:19:49Z",
            "hostname": "127.0.0.1",
            "score": 0.2,
            "action": "test",
        }
        responses.add(
            responses.POST,
            settings.GOOGLE_CAPTCHA_ENDPOINT,
            json.dumps(response),
            status=200,
        )
        self.assertFalse(is_human(client_side_token='a', captcha_type='v3'))

    @responses.activate
    def test_is_human_true_v3(self):
        response = {
            "success": True,
            "challenge_ts": "2022-12-24T12:19:49Z",
            "hostname": "127.0.0.1",
            "score": 0.8,
            "action": "test",
        }
        responses.add(
            responses.POST,
            settings.GOOGLE_CAPTCHA_ENDPOINT,
            json.dumps(response),
            status=200,
        )
        self.assertTrue(is_human(client_side_token='a', captcha_type='v3'))

    @responses.activate
    def test_is_human_true_v2(self):
        response = {
            "success": True,
            "challenge_ts": "2022-12-24T12:19:49Z",
            "hostname": "127.0.0.1",
            "score": 0.8,
            "action": "test",
        }
        responses.add(
            responses.POST,
            settings.GOOGLE_CAPTCHA_ENDPOINT,
            json.dumps(response),
            status=200,
        )
        self.assertTrue(is_human(client_side_token='a'))

    @responses.activate
    def test_is_human_google_error_code(self):
        response = {"success": False, "error-codes": ['timeout-or-duplicate']}
        responses.add(
            responses.POST,
            settings.GOOGLE_CAPTCHA_ENDPOINT,
            json.dumps(response),
            status=200,
        )
        self.assertFalse(is_human(client_side_token='a'))
