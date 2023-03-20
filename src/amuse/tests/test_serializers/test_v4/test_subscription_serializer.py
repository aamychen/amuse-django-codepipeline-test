import json
from unittest import mock

import responses
from django.conf import settings
from django.test import TestCase

from amuse.api.v4.serializers.subscription import (
    ChangeSubscriptionSerializer,
    CurrentSubscriptionSerializer,
    SubscriptionSerializer,
)
from amuse.tests.helpers import add_zendesk_mock_post_response
from amuse.tests.test_api.base import AmuseAPITestCase
from amuse.tests.test_vendor.test_adyen.base import AdyenBaseTestCase
from amuse.tests.test_vendor.test_adyen.helpers import (
    mock_country_check_unsupported_payment_details,
    mock_payment_details,
)
from amuse.utils import CLIENT_ANDROID
from countries.tests.factories import CountryFactory
from payments.tests.factories import PaymentTransactionFactory
from subscriptions.tests.factories import SubscriptionFactory, SubscriptionPlanFactory
from users.tests.factories import UserFactory


class TestSubscriptionSerializer(AmuseAPITestCase, AdyenBaseTestCase):
    @responses.activate
    def setUp(self):
        add_zendesk_mock_post_response()
        self.country = CountryFactory(code="SE", is_adyen_enabled=True)
        self.plan = SubscriptionPlanFactory()
        self.data = {
            "country": "SE",
            "plan": self.plan.pk,
            "payment_details": mock_payment_details(),
        }

        self.user = UserFactory()
        self.serializer = SubscriptionSerializer(
            data=self.data, context={'request': mock.Mock(user=self.user)}
        )

    @responses.activate
    def test_country_check_adyen_api_error(self):
        self._add_country_check_response(
            response=json.dumps(mock_country_check_unsupported_payment_details()),
            status_code=500,
        )

        assert not self.serializer.is_valid()
        self.assertEqual(len(self.serializer.errors["country"]), 1)
        self.assertEqual(
            str(self.serializer.errors["country"][0]), "Payment country lookup failed"
        )

    @responses.activate
    def test_selected_country_does_not_match_issuer_country_returns_mismatch_error(
        self,
    ):
        CountryFactory(code="IT", is_adyen_enabled=True)
        self._add_country_check_response("IT")

        assert not self.serializer.is_valid()
        self.assertEqual(len(self.serializer.errors["country"]), 1)
        assert "Card is from different country than you selected." in str(
            self.serializer.errors["country"][0]
        )

    @responses.activate
    def test_no_issuer_country_available_sets_user_given_country(self):
        self._add_country_check_response(None)

        assert self.serializer.is_valid()
        self.assertEqual(self.serializer.validated_data['country'], self.country)

    @responses.activate
    def test_issuer_country_unknown_sets_user_given_country(self):
        self._add_country_check_response("unknown")

        assert self.serializer.is_valid()
        self.assertEqual(self.serializer.validated_data["country"], self.country)

    @responses.activate
    def test_invalid_url_raises_validation_error(self):
        self.data['return_url'] = 'https://4mU53.com/'

        self.assertFalse(self.serializer.is_valid())
        self.assertEqual(self.serializer.errors["return_url"][0], 'Invalid return_url')

    @responses.activate
    def test_valid_android_url_accepted(self):
        self._add_country_check_response("unknown")
        url = 'adyencheckout://io.amuse.debug.2.0'
        self.data['return_url'] = url

        self.assertTrue(self.serializer.is_valid())
        self.assertEqual(self.serializer.validated_data['return_url'], url)

    @responses.activate
    def test_valid_web_url_accepted(self):
        self._add_country_check_response("unknown")
        url = settings.APP_URL + 'hello'
        self.data['return_url'] = url

        self.assertTrue(self.serializer.is_valid())
        self.assertEqual(self.serializer.validated_data['return_url'], url)

    @responses.activate
    def test_valid_amuse_io_url_accepted(self):
        self._add_country_check_response("unknown")
        url = 'https://amuse.io/hej'
        self.data['return_url'] = url

        self.assertTrue(self.serializer.is_valid())
        self.assertEqual(self.serializer.validated_data['return_url'], url)

    @responses.activate
    @mock.patch('amuse.api.v4.serializers.subscription.create_subscription')
    def test_android_client_identified_correctly(self, mocked_create_subscription):
        self._add_country_check_response("unknown")
        serializer = SubscriptionSerializer(
            data=self.data,
            context={
                'request': mock.Mock(
                    user=self.user,
                    META={'HTTP_USER_AGENT': 'amuse-Android/1.2.3; WiFi'},
                )
            },
        )
        mock_payment = mock_payment_details()

        self.assertTrue(serializer.is_valid())
        serializer.save()

        mocked_create_subscription.assert_called_once_with(
            user=self.user,
            subscription_plan=self.plan,
            payment_details=mock_payment['paymentMethod'],
            country=self.country,
            client=CLIENT_ANDROID,
            ip=None,
            browser_info=mock_payment['browserInfo'],
            force_3ds=True,
            return_url=None,
        )


class CurrentSubscriptionSerializerTestCase(AmuseAPITestCase):
    def setUp(self):
        super().setUp()
        self.plan = SubscriptionPlanFactory(trial_days=0)
        self.payment = PaymentTransactionFactory(subscription__plan=self.plan)
        self.subscription = self.payment.subscription
        self.payment_method = self.subscription.payment_method

    def test_serialize_existing_subscription(self):
        serializer = CurrentSubscriptionSerializer(self.subscription)
        self.assertEqual(
            serializer.data["paid_until"], self.payment.paid_until.strftime("%Y-%m-%d")
        )
        self.assertEqual(serializer.data["plan"]["id"], self.subscription.plan_id)
        self.assertEqual(serializer.data["provider"], self.subscription.provider)
        self.assertEqual(
            serializer.data["valid_from"],
            self.subscription.valid_from.strftime("%Y-%m-%d"),
        )
        self.assertIsNone(serializer.data["valid_until"])
        self.assertEqual(serializer.data["payment_method"], self.payment_method.method)
        self.assertEqual(
            serializer.data["payment_summary"], self.payment_method.summary
        )
        self.assertEqual(
            serializer.data["payment_expiry_date"],
            self.payment_method.expiry_date.strftime("%Y-%m-%d"),
        )

    def test_serialize_existing_subscription_without_payment_method(self):
        self.subscription.payment_method = None
        self.subscription.save()
        serializer = CurrentSubscriptionSerializer(self.subscription)

        self.assertIsNone(serializer.data["payment_method"])
        self.assertIsNone(serializer.data["payment_summary"])
        self.assertIsNone(serializer.data["payment_expiry_date"])


class ChangeSubscriptionSerializerTestCase(TestCase):
    def setUp(self):
        self.plan = SubscriptionPlanFactory(is_public=True)
        self.subscription = SubscriptionFactory()
        self.serializer = ChangeSubscriptionSerializer(data={'plan': self.plan.pk})

    def test_success(self):
        assert self.serializer.is_valid()

    def test_hidden_subscription_raises_error(self):
        self.plan.is_public = False
        self.plan.save()

        assert not self.serializer.is_valid()
