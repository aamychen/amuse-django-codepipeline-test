import datetime
import responses
from django.test import TestCase, override_settings
from payments.tests.factories import PaymentTransactionFactory
from payments.reporting_utils import ReportingUtils
from amuse.tests.helpers import (
    add_zendesk_mock_post_response,
    ZENDESK_MOCK_API_URL_TOKEN,
)


class ForTesting:
    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)


@override_settings(**ZENDESK_MOCK_API_URL_TOKEN)
class TestReportingUtils(TestCase):
    @responses.activate
    def setUp(self):
        add_zendesk_mock_post_response()
        self.util = ReportingUtils()
        self.payment = PaymentTransactionFactory()

    def test_date_from_string(self):
        string_date = '2021-04-23'
        date_object = self.util.get_date_form_string(string_date)
        self.assertIsInstance(date_object, datetime.date)
        self.assertEqual(
            self.util.get_date_form_string(date_string=""),
            datetime.datetime.now().date(),
        )
        self.assertEqual(
            self.util.get_date_form_string(date_string=None),
            datetime.datetime.now().date(),
        )

    def test_get_prefix(self):
        prefix = self.util.get_report_prefix()
        self.assertTrue(isinstance(prefix, int))

    def test_data_formatter(self):
        test_object = ForTesting(int_value=10, timestamp_value=datetime.datetime.now())
        self.assertEqual(self.util.data_formatter(test_object, 'int_value'), 10)
        self.assertEqual(
            self.util.data_formatter(test_object, 'timestamp_value'),
            datetime.datetime.now().date(),
        )
        self.assertIsInstance(self.util.data_formatter(self.payment, 'category'), str)
        self.assertIsInstance(self.util.data_formatter(self.payment, 'platform'), str)
        self.assertIsInstance(
            self.util.data_formatter(self.payment, 'subscription'), str
        )
