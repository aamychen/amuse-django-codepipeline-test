from django.test import TestCase
from hyperwallet.exceptions import HyperwalletAPIException, HyperwalletException
from payouts.utils import get_hw_exception_code


class TestGetErrorCode(TestCase):
    def setUp(self):
        self.hw_exception = HyperwalletException(
            {
                'errors': [
                    {
                        'code': 'COMMUNICATION_ERROR',
                        'message': "Connection to https://api.paylution.com failed: ('Connection aborted.', ConnectionResetError(104, 'Connection reset by peer'))",
                    }
                ]
            }
        )
        self.hw_api_exception = HyperwalletAPIException(
            {
                "errors": [
                    {
                        "message": "PayPal transfer method email address should be same as profile email address.",
                        "code": "CONSTRAINT_VIOLATIONS",
                    }
                ]
            }
        )

    def test_get_hw_exception_code(self):
        hw_error_code = get_hw_exception_code(self.hw_exception)
        hw_api_error_code = get_hw_exception_code(self.hw_api_exception)
        parser_error = get_hw_exception_code(Exception("Wrong format"))

        self.assertEqual(hw_error_code, 'COMMUNICATION_ERROR')
        self.assertEqual(hw_api_error_code, 'CONSTRAINT_VIOLATIONS')
        self.assertEqual(parser_error, 'EXCEPTION_PARSER_ERROR')
