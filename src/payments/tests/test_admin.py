from unittest import mock
from datetime import datetime, timezone
import json

from django.http import HttpResponseRedirect
from django.urls import reverse
from django.contrib import admin
from django.contrib.messages import get_messages, SUCCESS, ERROR
from django.test import override_settings, TestCase
import responses

from amuse.tests.helpers import (
    add_zendesk_mock_post_response,
    ZENDESK_MOCK_API_URL_TOKEN,
)
from countries.tests.factories import CountryFactory
from payments.admin import PaymentTransactionAdmin
from payments.models import PaymentTransaction
from payments.services.moss import MossReportException
from payments.tests.factories import PaymentTransactionFactory
from subscriptions.models import Subscription
from subscriptions.tests.factories import SubscriptionFactory, SubscriptionPlanFactory
from users.tests.factories import UserFactory
from users.models import User


@override_settings(**ZENDESK_MOCK_API_URL_TOKEN)
class PaymentAdminTest(TestCase):
    @responses.activate
    def test_payment_transaction_extra_columns(self):
        add_zendesk_mock_post_response()
        ios_subscription = SubscriptionFactory(provider=Subscription.PROVIDER_IOS)
        ios_transaction = PaymentTransactionFactory(subscription=ios_subscription)
        adyen_id = 'data9000'
        adyen_transaction = PaymentTransactionFactory(external_transaction_id=adyen_id)

        a = PaymentTransactionAdmin(PaymentTransaction, admin.site)

        self.assertEqual(a.external_url(ios_transaction), '')
        self.assertIn(adyen_id, a.external_url(adyen_transaction))
        self.assertEqual(a.email(ios_transaction), ios_transaction.user.email)


@override_settings(**ZENDESK_MOCK_API_URL_TOKEN)
class AdyenRefundPaymentAction(TestCase):
    @responses.activate
    def setUp(self):
        add_zendesk_mock_post_response()
        admin_user = UserFactory(is_staff=True, category=User.CATEGORY_DEFAULT)
        self.user = UserFactory()
        self.client.force_login(user=admin_user)
        self.plan = SubscriptionPlanFactory(trial_days=0)
        self.payment = PaymentTransactionFactory(
            amount=50, plan=self.plan, user=self.user
        )

        self.url = reverse("admin:payments_paymenttransaction_changelist")

    @responses.activate
    def test_success(self):
        responses.add(
            responses.POST,
            "https://pal-test.adyen.com/pal/servlet/Payment/v49/refund",
            json.dumps(
                {'pspReference': '862618593929080C', 'response': '[refund-received]'}
            ),
            status=200,
        )

        data = {
            "action": "adyen_refund",
            '_selected_action': [self.payment.pk],
            'confirm': 'yes',
        }
        response = self.client.post(self.url, data)
        messages = list(get_messages(response.wsgi_request))

        self.assertEqual(len(messages), 1)
        self.assertEqual(messages[0].level, SUCCESS)

    @responses.activate
    def test_failed(self):
        responses.add(
            responses.POST,
            "https://pal-test.adyen.com/pal/servlet/Payment/v49/refund",
            json.dumps(
                {
                    "status": 422,
                    "errorCode": "167",
                    "message": "Original pspReference required for this operation",
                    "errorType": "validation",
                }
            ),
            status=442,
        )

        data = {
            "action": "adyen_refund",
            '_selected_action': [self.payment.pk],
            'confirm': 'yes',
        }
        response = self.client.post(self.url, data)
        messages = list(get_messages(response.wsgi_request))

        self.assertEqual(len(messages), 1)
        self.assertEqual(messages[0].level, ERROR)


@override_settings(**ZENDESK_MOCK_API_URL_TOKEN)
class DowloadCSVPaymentAction(TestCase):
    @responses.activate
    def setUp(self):
        add_zendesk_mock_post_response()
        admin_user = UserFactory(is_staff=True, category=User.CATEGORY_DEFAULT)
        self.user = UserFactory()
        self.client.force_login(user=admin_user)
        self.plan = SubscriptionPlanFactory(trial_days=0)
        self.payment = PaymentTransactionFactory(
            amount=50, plan=self.plan, user=self.user
        )
        self.url = reverse("admin:payments_paymenttransaction_changelist")

    @responses.activate
    def test_success(self):
        data = {
            "action": "export_to_csv",
            '_selected_action': [self.payment.pk],
            'confirm': 'yes',
        }
        response = self.client.post(self.url, data)
        messages = list(get_messages(response.wsgi_request))
        self.assertEqual(response.status_code, 200)

        self.assertEqual(len(messages), 1)
        self.assertEqual(messages[0].level, SUCCESS)


@override_settings(**ZENDESK_MOCK_API_URL_TOKEN)
class PaymentMossReportTest(TestCase):
    @responses.activate
    def setUp(self) -> None:
        add_zendesk_mock_post_response()
        self.admin_user = UserFactory(is_staff=True)
        self.user = UserFactory()
        self.plan = SubscriptionPlanFactory()
        self.country_sweden = CountryFactory(code='SE', name='Sweden')
        self.country_austria = CountryFactory(code='AT', name='Austria')
        PaymentTransactionFactory(
            amount=100,
            vat_amount=10,
            vat_percentage=0.1,
            country=self.country_sweden,
            created=datetime(2022, 1, 6, 15, 15, 15, tzinfo=timezone.utc),
        )
        PaymentTransactionFactory(
            amount=50,
            vat_amount=5,
            vat_percentage=0.1,
            country=self.country_austria,
            created=datetime(2022, 1, 6, 16, 16, 16, tzinfo=timezone.utc),
        )
        self.client.force_login(user=self.admin_user)
        self.url = reverse("admin:payments_paymenttransaction_moss")

    @mock.patch("payments.services.moss.MossReport.generate_report")
    @mock.patch("payments.services.moss.MossReport.__init__", return_value=None)
    def test_sweden_report_success(
        self, mock_moss_report_init, mock_moss_generate_report
    ):
        data = {'period_month': '1', 'period_year': '2022', 'countries': '0'}
        generated_filename = "moss_2022_1_SE.csv"
        response = self.client.post(self.url, data)
        mock_moss_report_init.assert_called_with(
            2022, 1, country=self.country_sweden.code
        )
        mock_moss_generate_report.assert_called_with(response)
        self.assertIn(generated_filename, response['Content-Disposition'])

    @mock.patch("payments.services.moss.MossReport.generate_report")
    @mock.patch("payments.services.moss.MossReport.__init__", return_value=None)
    def test_rest_of_the_world_report_success(
        self, mock_moss_report_init, mock_moss_generate_report
    ):
        data = {'period_month': '1', 'period_year': '2022', 'countries': '1'}
        generated_filename = "moss_2022_1_ROW.csv"
        response = self.client.post(self.url, data)
        mock_moss_report_init.assert_called_with(2022, 1, country=None)
        mock_moss_generate_report.assert_called_with(response)
        self.assertIn(generated_filename, response['Content-Disposition'])

    @mock.patch(
        "payments.services.moss.MossReport.generate_report",
        side_effect=MossReportException('Exception raised.'),
    )
    @mock.patch("payments.services.moss.MossReport.__init__", return_value=None)
    def test_failed(self, mock_moss_report_init, mock_moss_generate_report):
        data = {'period_month': '1', 'period_year': '2022', 'countries': '0'}
        response = self.client.post(self.url, data)
        mock_moss_report_init.assert_called_with(
            2022, 1, country=self.country_sweden.code
        )

        messages = list(get_messages(response.wsgi_request))
        self.assertEqual(len(messages), 1)
        self.assertEqual(messages[0].level, ERROR)

        self.assertEqual(response.status_code, 302)
        self.assertTrue(isinstance(response, HttpResponseRedirect))
        self.assertRedirects(
            response, response.wsgi_request.get_full_path(), status_code=302
        )
