from datetime import datetime, timedelta
from decimal import Decimal
from unittest import mock

import httplib2
import pytest
import responses
from django.contrib import admin
from django.contrib.messages import get_messages, SUCCESS, ERROR
from django.forms import ValidationError
from django.test import override_settings, TestCase
from django.test.client import RequestFactory
from django.urls import reverse
from django.utils import timezone
from googleapiclient.errors import HttpError

from amuse.tests.helpers import (
    add_zendesk_mock_post_response,
    ZENDESK_MOCK_API_URL_TOKEN,
)
from countries.tests.factories import CountryFactory, CurrencyFactory
from payments.tests.factories import PaymentMethodFactory
from subscriptions.admin import (
    SubscriptionAdmin,
    SubscriptionForm,
    GoogleActionHelper,
    GoogleSubscriptionActionError,
    GoogleRecreateForm,
    GoogleRecreateHelper,
    PriceCardValidator,
    PriceCardAdminForm,
    IntroductoryPriceCardAdminForm,
)
from subscriptions.models import Subscription
from subscriptions.tests.factories import (
    SubscriptionFactory,
    SubscriptionPlanFactory,
    PriceCardFactory,
    IntroductoryPriceCardFactory,
)
from subscriptions.vendor.google.google_play_api import GooglePlayAPI
from users.models import User
from users.tests.factories import UserFactory


@override_settings(**ZENDESK_MOCK_API_URL_TOKEN)
class SubscriptionAdminTest(TestCase):
    @responses.activate
    def test_payment_transaction_extra_columns(self):
        add_zendesk_mock_post_response()
        subscription = SubscriptionFactory(provider=Subscription.PROVIDER_IOS)

        a = SubscriptionAdmin(Subscription, admin.site)

        self.assertEqual(a.email(subscription), subscription.user.email)
        self.assertEqual(a.status_list_display(subscription), 'Active')


class SubscriptionFormTest(TestCase):
    @responses.activate
    @mock.patch("amuse.tasks.zendesk_create_or_update_user")
    def test_clean_raise_error_for_non_google_subscription(self, _):
        form = SubscriptionForm()
        form.instance = SubscriptionFactory(provider=Subscription.PROVIDER_GOOGLE)
        with self.assertRaises(ValidationError):
            form.clean()


class GoogleSubscriptionCancelAction(TestCase):
    @responses.activate
    @mock.patch("amuse.tasks.zendesk_create_or_update_user")
    def setUp(self, _):
        admin_user = UserFactory(is_staff=True, category=User.CATEGORY_DEFAULT)
        self.client.force_login(user=admin_user)

        self.url = reverse("admin:subscriptions_subscription_changelist")

    @responses.activate
    @mock.patch("amuse.tasks.zendesk_create_or_update_user")
    @mock.patch.object(GoogleActionHelper, 'cancel')
    def test_success(self, mock_action, _):
        sub = SubscriptionFactory(provider=Subscription.PROVIDER_GOOGLE)
        data = {
            "action": "cancel_google_subscription",
            '_selected_action': [sub.id],
            'confirm': 'yes',
        }
        response = self.client.post(self.url, data)
        messages = list(get_messages(response.wsgi_request))

        mock_action.assert_called_once()
        self.assertEqual(len(messages), 1)
        self.assertEqual(messages[0].level, SUCCESS)

    @responses.activate
    @mock.patch("amuse.tasks.zendesk_create_or_update_user")
    @mock.patch.object(GoogleActionHelper, 'cancel')
    def test_fail_for_multiple_selected_itemw(self, mock_action, _):
        sub1 = SubscriptionFactory(provider=Subscription.PROVIDER_GOOGLE)
        sub2 = SubscriptionFactory(provider=Subscription.PROVIDER_GOOGLE)

        url = reverse("admin:subscriptions_subscription_changelist")
        data = {
            "action": "cancel_google_subscription",
            '_selected_action': [sub1.id, sub2.id],
            'confirm': 'yes',
        }
        response = self.client.post(self.url, data)
        messages = list(get_messages(response.wsgi_request))

        self.assertEqual(0, mock_action.call_count)
        self.assertEqual(1, len(messages))
        self.assertEqual(ERROR, messages[0].level)

    @responses.activate
    @mock.patch("amuse.tasks.zendesk_create_or_update_user")
    @mock.patch.object(GoogleActionHelper, 'cancel')
    def test_fail_for_non_google_sub(self, mock_action, _):
        sub1 = SubscriptionFactory(provider=Subscription.PROVIDER_IOS)

        url = reverse("admin:subscriptions_subscription_changelist")
        data = {
            "action": "cancel_google_subscription",
            '_selected_action': [sub1.id],
            'confirm': 'yes',
        }
        response = self.client.post(self.url, data)
        messages = list(get_messages(response.wsgi_request))

        self.assertEqual(0, mock_action.call_count)
        self.assertEqual(1, len(messages))
        self.assertEqual(ERROR, messages[0].level)

    @responses.activate
    @mock.patch("amuse.tasks.zendesk_create_or_update_user")
    @mock.patch.object(GoogleActionHelper, 'cancel')
    def test_show_dialog(self, mock_action, _):
        sub1 = SubscriptionFactory(provider=Subscription.PROVIDER_GOOGLE)

        url = reverse("admin:subscriptions_subscription_changelist")
        data = {"action": "cancel_google_subscription", '_selected_action': [sub1.id]}
        response = self.client.post(self.url, data, follow=True)

        self.assertTemplateUsed(
            response, 'admin/subscriptions/subscription/google_subscription_action.html'
        )


class GoogleSubscriptionDeferAction(TestCase):
    @responses.activate
    @mock.patch("amuse.tasks.zendesk_create_or_update_user")
    def setUp(self, _):
        admin_user = UserFactory(is_staff=True, category=User.CATEGORY_DEFAULT)
        self.client.force_login(user=admin_user)

        self.url = reverse("admin:subscriptions_subscription_changelist")

    @responses.activate
    @mock.patch("amuse.tasks.zendesk_create_or_update_user")
    @mock.patch.object(GoogleActionHelper, 'defer')
    @mock.patch.object(Subscription, 'paid_until')
    def test_success(self, mock_paid_until, mock_action, _):
        mock_paid_until.return_value = datetime.today() + timedelta(days=5)
        sub = SubscriptionFactory(provider=Subscription.PROVIDER_GOOGLE)
        data = {
            "action": "defer_google_subscription",
            '_selected_action': [sub.id],
            'confirm': 'yes',
            'defer_date': str((datetime.today() + timedelta(days=10)).date()),
        }
        response = self.client.post(self.url, data)
        messages = list(get_messages(response.wsgi_request))

        mock_action.assert_called_once()
        self.assertEqual(len(messages), 1)
        self.assertEqual(messages[0].level, SUCCESS)

    @responses.activate
    @mock.patch("amuse.tasks.zendesk_create_or_update_user")
    @mock.patch.object(GoogleActionHelper, 'defer')
    def test_fail_for_multiple_selected_items(self, mock_action, _):
        sub1 = SubscriptionFactory(provider=Subscription.PROVIDER_GOOGLE)
        sub2 = SubscriptionFactory(provider=Subscription.PROVIDER_GOOGLE)

        url = reverse("admin:subscriptions_subscription_changelist")
        data = {
            "action": "defer_google_subscription",
            '_selected_action': [sub1.id, sub2.id],
            'confirm': 'yes',
        }
        response = self.client.post(self.url, data)
        messages = list(get_messages(response.wsgi_request))

        self.assertEqual(0, mock_action.call_count)
        self.assertEqual(1, len(messages))
        self.assertEqual(ERROR, messages[0].level)

    @responses.activate
    @mock.patch("amuse.tasks.zendesk_create_or_update_user")
    @mock.patch.object(GoogleActionHelper, 'defer')
    def test_fail_for_non_google_sub(self, mock_action, _):
        sub1 = SubscriptionFactory(provider=Subscription.PROVIDER_IOS)

        url = reverse("admin:subscriptions_subscription_changelist")
        data = {
            "action": "defer_google_subscription",
            '_selected_action': [sub1.id],
            'confirm': 'yes',
        }
        response = self.client.post(self.url, data)
        messages = list(get_messages(response.wsgi_request))

        self.assertEqual(0, mock_action.call_count)
        self.assertEqual(1, len(messages))
        self.assertEqual(ERROR, messages[0].level)

    @responses.activate
    @mock.patch("amuse.tasks.zendesk_create_or_update_user")
    @mock.patch.object(GoogleActionHelper, 'defer')
    def test_show_dialog(self, mock_action, _):
        sub1 = SubscriptionFactory(provider=Subscription.PROVIDER_GOOGLE)

        url = reverse("admin:subscriptions_subscription_changelist")
        data = {"action": "defer_google_subscription", '_selected_action': [sub1.id]}
        response = self.client.post(self.url, data, follow=True)

        self.assertTemplateUsed(
            response, 'admin/subscriptions/subscription/google_defer_action.html'
        )


class GoogleSubscriptionRefundAction(TestCase):
    @responses.activate
    @mock.patch("amuse.tasks.zendesk_create_or_update_user")
    def setUp(self, _):
        admin_user = UserFactory(is_staff=True, category=User.CATEGORY_DEFAULT)
        self.client.force_login(user=admin_user)

        self.url = reverse("admin:subscriptions_subscription_changelist")

    @responses.activate
    @mock.patch("amuse.tasks.zendesk_create_or_update_user")
    @mock.patch.object(GoogleActionHelper, 'refund')
    def test_success(self, mock_action, _):
        sub = SubscriptionFactory(provider=Subscription.PROVIDER_GOOGLE)
        data = {
            "action": "refund_google_subscription",
            '_selected_action': [sub.id],
            'confirm': 'yes',
        }
        response = self.client.post(self.url, data)
        messages = list(get_messages(response.wsgi_request))

        mock_action.assert_called_once()
        self.assertEqual(len(messages), 1)
        self.assertEqual(messages[0].level, SUCCESS)

    @responses.activate
    @mock.patch("amuse.tasks.zendesk_create_or_update_user")
    @mock.patch.object(GoogleActionHelper, 'refund')
    def test_fail_for_multiple_selected_itemw(self, mock_action, _):
        sub1 = SubscriptionFactory(provider=Subscription.PROVIDER_GOOGLE)
        sub2 = SubscriptionFactory(provider=Subscription.PROVIDER_GOOGLE)

        url = reverse("admin:subscriptions_subscription_changelist")
        data = {
            "action": "refund_google_subscription",
            '_selected_action': [sub1.id, sub2.id],
            'confirm': 'yes',
        }
        response = self.client.post(self.url, data)
        messages = list(get_messages(response.wsgi_request))

        self.assertEqual(0, mock_action.call_count)
        self.assertEqual(1, len(messages))
        self.assertEqual(ERROR, messages[0].level)

    @responses.activate
    @mock.patch("amuse.tasks.zendesk_create_or_update_user")
    @mock.patch.object(GoogleActionHelper, 'refund')
    def test_fail_for_non_google_sub(self, mock_action, _):
        sub1 = SubscriptionFactory(provider=Subscription.PROVIDER_IOS)

        url = reverse("admin:subscriptions_subscription_changelist")
        data = {
            "action": "refund_google_subscription",
            '_selected_action': [sub1.id],
            'confirm': 'yes',
        }
        response = self.client.post(self.url, data)
        messages = list(get_messages(response.wsgi_request))

        self.assertEqual(0, mock_action.call_count)
        self.assertEqual(1, len(messages))
        self.assertEqual(ERROR, messages[0].level)

    @responses.activate
    @mock.patch("amuse.tasks.zendesk_create_or_update_user")
    @mock.patch.object(GoogleActionHelper, 'refund')
    def test_show_dialog(self, mock_action, _):
        sub1 = SubscriptionFactory(provider=Subscription.PROVIDER_GOOGLE)

        url = reverse("admin:subscriptions_subscription_changelist")
        data = {"action": "refund_google_subscription", '_selected_action': [sub1.id]}
        response = self.client.post(self.url, data, follow=True)

        self.assertTemplateUsed(
            response, 'admin/subscriptions/subscription/google_subscription_action.html'
        )


class GoogleSubscriptionRevokeAction(TestCase):
    @responses.activate
    @mock.patch("amuse.tasks.zendesk_create_or_update_user")
    def setUp(self, _):
        admin_user = UserFactory(is_staff=True, category=User.CATEGORY_DEFAULT)
        self.client.force_login(user=admin_user)

        self.url = reverse("admin:subscriptions_subscription_changelist")

    @responses.activate
    @mock.patch("amuse.tasks.zendesk_create_or_update_user")
    @mock.patch.object(GoogleActionHelper, 'revoke')
    def test_success(self, mock_action, _):
        sub = SubscriptionFactory(provider=Subscription.PROVIDER_GOOGLE)
        data = {
            "action": "revoke_google_subscription",
            '_selected_action': [sub.id],
            'confirm': 'yes',
        }
        response = self.client.post(self.url, data)
        messages = list(get_messages(response.wsgi_request))

        mock_action.assert_called_once()
        self.assertEqual(len(messages), 1)
        self.assertEqual(messages[0].level, SUCCESS)

    @responses.activate
    @mock.patch("amuse.tasks.zendesk_create_or_update_user")
    @mock.patch.object(GoogleActionHelper, 'revoke')
    def test_fail_for_multiple_selected_itemw(self, mock_action, _):
        sub1 = SubscriptionFactory(provider=Subscription.PROVIDER_GOOGLE)
        sub2 = SubscriptionFactory(provider=Subscription.PROVIDER_GOOGLE)

        url = reverse("admin:subscriptions_subscription_changelist")
        data = {
            "action": "revoke_google_subscription",
            '_selected_action': [sub1.id, sub2.id],
            'confirm': 'yes',
        }
        response = self.client.post(self.url, data)
        messages = list(get_messages(response.wsgi_request))

        self.assertEqual(0, mock_action.call_count)
        self.assertEqual(1, len(messages))
        self.assertEqual(ERROR, messages[0].level)

    @responses.activate
    @mock.patch("amuse.tasks.zendesk_create_or_update_user")
    @mock.patch.object(GoogleActionHelper, 'revoke')
    def test_fail_for_non_google_sub(self, mock_action, _):
        sub1 = SubscriptionFactory(provider=Subscription.PROVIDER_IOS)

        url = reverse("admin:subscriptions_subscription_changelist")
        data = {
            "action": "revoke_google_subscription",
            '_selected_action': [sub1.id],
            'confirm': 'yes',
        }
        response = self.client.post(self.url, data)
        messages = list(get_messages(response.wsgi_request))

        self.assertEqual(0, mock_action.call_count)
        self.assertEqual(1, len(messages))
        self.assertEqual(ERROR, messages[0].level)

    @responses.activate
    @mock.patch("amuse.tasks.zendesk_create_or_update_user")
    @mock.patch.object(GoogleActionHelper, 'revoke')
    def test_show_dialog(self, mock_action, _):
        sub1 = SubscriptionFactory(provider=Subscription.PROVIDER_GOOGLE)

        url = reverse("admin:subscriptions_subscription_changelist")
        data = {"action": "revoke_google_subscription", '_selected_action': [sub1.id]}
        response = self.client.post(self.url, data, follow=True)

        self.assertTemplateUsed(
            response, 'admin/subscriptions/subscription/google_subscription_action.html'
        )


class GoogleActionHelperValidatorsTestCase(TestCase):
    def test_is_confirmed_by_jarvi5_user(self):
        post = RequestFactory().post('/fake/url', data={'confirm': 'yes'})
        actual = GoogleActionHelper().is_confirmed_by_jarvi5_user(request=post)
        self.assertTrue(actual)

    def test_validate_defer_date(self):
        # empty string
        with self.assertRaises(GoogleSubscriptionActionError):
            GoogleActionHelper().validate_defer_date('')

        # none value
        with self.assertRaises(GoogleSubscriptionActionError):
            GoogleActionHelper().validate_defer_date(None)

        # invalid string
        with self.assertRaises(GoogleSubscriptionActionError):
            GoogleActionHelper().validate_defer_date('2018/10/07')

    @responses.activate
    @mock.patch("amuse.tasks.zendesk_create_or_update_user")
    def test_validate_google_provider(self, _):
        SubscriptionFactory(provider=Subscription.PROVIDER_GOOGLE)

        actual = GoogleActionHelper().validate_google_provider(Subscription.objects)
        self.assertIsNone(actual)

    @responses.activate
    @mock.patch("amuse.tasks.zendesk_create_or_update_user")
    def test_validate_google_provider_raise_an_error(self, _):
        SubscriptionFactory(provider=Subscription.PROVIDER_ADYEN)

        with pytest.raises(GoogleSubscriptionActionError) as err:
            GoogleActionHelper().validate_google_provider(Subscription.objects)

        expected = 'Please, select Google subscription.'
        self.assertEqual(expected, str(err.value))

    @responses.activate
    @mock.patch("amuse.tasks.zendesk_create_or_update_user")
    @mock.patch.object(Subscription, "is_free", return_value=True)
    def test_validate_paid_until(self, _, __):
        SubscriptionFactory()

        with pytest.raises(GoogleSubscriptionActionError) as err:
            GoogleActionHelper().validate_paid_until(Subscription.objects)

        expected = 'Unable to change subscription. Invalid paid_until date.'
        self.assertEqual(expected, str(err.value))

    def test_validate_purchase(self):
        with self.assertRaises(GoogleSubscriptionActionError):
            GoogleActionHelper().validate_purchase('123', None)

    @responses.activate
    @mock.patch("amuse.tasks.zendesk_create_or_update_user")
    def test_validate_single_item_selected(self, _):
        SubscriptionFactory()

        actual = GoogleActionHelper().validate_single_item_selected(
            Subscription.objects
        )
        self.assertIsNone(actual)

    @responses.activate
    @mock.patch("amuse.tasks.zendesk_create_or_update_user")
    def test_validate_single_item_selected_raise_an_error(self, _):
        SubscriptionFactory()
        SubscriptionFactory()

        with pytest.raises(GoogleSubscriptionActionError) as err:
            GoogleActionHelper().validate_single_item_selected(Subscription.objects)

        expected = 'Please, select only one Google subscription.'
        self.assertEqual(expected, str(err.value))

    def test_validate_result(self):
        actual = GoogleActionHelper().validate_result('123', dict(success=True))

        self.assertIsNone(actual)

    def test_validate_result_raise_an_error(self):
        with pytest.raises(GoogleSubscriptionActionError) as err:
            GoogleActionHelper().validate_result(
                '123', dict(success=False, message='Oh no!')
            )

        expected = "Event ID=123. Google: Oh no!"
        self.assertEqual(expected, str(err.value))


class GoogleActionHelperTestCase(TestCase):
    @responses.activate
    @mock.patch("amuse.tasks.zendesk_create_or_update_user")
    def setUp(self, _):
        plan = SubscriptionPlanFactory(google_product_id='google_sub')
        payment_method = PaymentMethodFactory(external_recurring_id='123')

        self.subscription = SubscriptionFactory(
            status=Subscription.STATUS_ACTIVE,
            provider=Subscription.PROVIDER_GOOGLE,
            payment_method=payment_method,
            plan=plan,
        )

    @mock.patch.object(GooglePlayAPI, 'cancel', return_value=dict(success=True))
    def test_cancel(self, mock_api):
        GoogleActionHelper().cancel(Subscription.objects)
        mock_api.assert_called_once()

    @mock.patch.object(GooglePlayAPI, 'verify_purchase_token')
    @mock.patch.object(GooglePlayAPI, 'defer', return_value=dict(success=True))
    def test_defer(self, mock_defer_api, mock_verify_api):
        expiration_date = datetime.today() + timedelta(days=10)
        defer_date = datetime.today() + timedelta(days=20)

        mock_verify_api.return_value = dict(
            expiryTimeMillis=str(expiration_date.timestamp() * 1000)
        )

        GoogleActionHelper().defer(Subscription.objects, str(defer_date.date()))
        mock_verify_api.assert_called_once()
        mock_defer_api.assert_called_once()

    @mock.patch.object(GooglePlayAPI, 'verify_purchase_token', return_value=None)
    @mock.patch.object(GooglePlayAPI, 'defer', return_value=dict(success=True))
    def test_defer_unsuccess_for_invalid_token(self, mock_defer_api, mock_verify_api):
        defer_date = datetime.today() + timedelta(days=20)

        with self.assertRaises(GoogleSubscriptionActionError):
            GoogleActionHelper().defer(Subscription.objects, str(defer_date.date()))

        mock_verify_api.assert_called_once()
        self.assertEqual(0, mock_defer_api.call_count)

    @mock.patch.object(GooglePlayAPI, 'refund', return_value=dict(success=True))
    def test_refund(self, mock_api):
        GoogleActionHelper().refund(Subscription.objects)
        mock_api.assert_called_once()

    @mock.patch.object(GooglePlayAPI, 'revoke', return_value=dict(success=True))
    def test_revoke(self, mock_api):
        GoogleActionHelper().revoke(Subscription.objects)
        mock_api.assert_called_once()

    def test_get_google_product_id(self):
        actual = GoogleActionHelper().get_google_product_id(self.subscription)
        expected = self.subscription.plan.google_product_id
        self.assertEqual(expected, actual)

    def test_get_google_product_id_for_free_trial_subscrition(self):
        self.subscription.free_trial_from = timezone.now() - timedelta(days=5)
        self.subscription.free_trial_until = timezone.now() + timedelta(days=5)

        actual = GoogleActionHelper().get_google_product_id(self.subscription)
        expected = self.subscription.plan.google_product_id_trial
        self.assertEqual(expected, actual)


class GoogleRecreateHelperTestCase(TestCase):
    def test_get_step(self):
        request = RequestFactory().get('/fake/url')
        self.assertEqual(
            GoogleRecreateHelper.StepEnum.INITIAL,
            GoogleRecreateHelper().get_step(request),
        )

        request = RequestFactory().post('/fake/url')
        self.assertEqual(
            GoogleRecreateHelper.StepEnum.VALIDATION,
            GoogleRecreateHelper().get_step(request),
        )

        request = RequestFactory().post('/fake/url', data={'step': '2'})
        self.assertEqual(
            GoogleRecreateHelper.StepEnum.CONFIRMATION,
            GoogleRecreateHelper().get_step(request),
        )

    @responses.activate
    @mock.patch("amuse.tasks.zendesk_create_or_update_user")
    @mock.patch.object(GooglePlayAPI, 'verify_purchase_token')
    def test_preview_items(self, mock_verify, _):
        user = UserFactory()
        plan = SubscriptionPlanFactory(google_product_id='amuse-boost-tier')
        mock_verify.return_value = {
            'orderId': 'ORDER123.456',
            'startTimeMillis': 1621330363,
            'expiryTimeMillis': 1621330363,
            'autoRenewing': 1,
            'priceAmountMicros': '1990000',
            'priceCurrencyCode': 'GBP',
            'countryCode': 'GB',
            'linkedPurchaseToken': None,
        }
        form = GoogleRecreateForm(
            {
                'user_id': user.pk,
                'google_product_id': plan.google_product_id,
                'purchase_token': 'purchaseToken13',
            }
        )

        self.assertTrue(form.is_valid())
        preview_items = GoogleRecreateHelper().preview_items(form)
        self.assertIsInstance(preview_items, list)
        self.assertEqual(10, len(preview_items))

    @responses.activate
    @mock.patch("amuse.tasks.zendesk_create_or_update_user")
    @mock.patch.object(GooglePlayAPI, 'verify_purchase_token')
    def test_create_subscription(self, mock_verify, _):
        country = CountryFactory(code='US')
        currency = CurrencyFactory(code='USD')
        user = UserFactory()
        plan = SubscriptionPlanFactory(google_product_id='amuse-boost-tier')

        mock_verify.return_value = {
            'orderId': 'ORDER123.456',
            'startTimeMillis': 1621330363,
            'expiryTimeMillis': 1621330363,
            'autoRenewing': 1,
            'priceAmountMicros': '1990000',
            'priceCurrencyCode': 'USD',
            'countryCode': 'US',
            'linkedPurchaseToken': None,
            'acknowledgementState': 1,
        }
        form = GoogleRecreateForm(
            {
                'user_id': user.pk,
                'google_product_id': plan.google_product_id,
                'purchase_token': 'purchaseToken13',
            }
        )

        self.assertTrue(form.is_valid())
        subscription = GoogleRecreateHelper().create_subscription(form)

        self.assertEqual(user, subscription.user)
        self.assertEqual(Subscription.STATUS_ACTIVE, subscription.status)

        payment = subscription.latest_payment()
        self.assertIsNotNone(payment)
        self.assertEqual(Decimal('1.99'), payment.amount)
        self.assertEqual(currency, payment.currency)
        self.assertEqual(country, payment.country)
        self.assertEqual('ORDER123.456', payment.external_transaction_id)


class GoogleRecreateFormTest(TestCase):
    @responses.activate
    @mock.patch("amuse.tasks.zendesk_create_or_update_user")
    @mock.patch.object(GooglePlayAPI, 'verify_purchase_token', return_value=None)
    def test_validate_errors(self, mock_verify_api, _):
        form = GoogleRecreateForm(
            {'user_id': 123, 'google_product_id': 123, 'purchase_token': 'xyz'}
        )

        expected_error = HttpError(
            httplib2.Response({"status": 500}), b'{"error": {"message": "Mock Error" }}'
        )
        self.assertEqual(
            '<HttpError 500 when requesting None returned "Mock Error". Details: "Mock Error">',
            str(expected_error),
        )
        mock_verify_api.side_effect = expected_error
        self.assertFalse(form.is_valid())

        errors = {
            'user_id': ['User does not exist.'],
            'google_product_id': ['Unknown Google Product ID.'],
            'purchase_token': ['Mock Error'],
        }
        self.assertEqual(3, len(form.errors))
        self.assertDictEqual(errors, form.errors)

        mock_verify_api.assert_called_once()

    @responses.activate
    @mock.patch("amuse.tasks.zendesk_create_or_update_user")
    @mock.patch.object(GooglePlayAPI, 'verify_purchase_token', return_value=None)
    def test_validate_payment_method(self, mock_verify_api, _):
        purchase_token = '123'
        google_product_id = 'google_sub'
        user = UserFactory()
        payment_method = PaymentMethodFactory(
            user=user, external_recurring_id=purchase_token
        )
        plan = SubscriptionPlanFactory(google_product_id=google_product_id)
        subscription = SubscriptionFactory(
            status=Subscription.STATUS_ACTIVE,
            provider=Subscription.PROVIDER_GOOGLE,
            payment_method=payment_method,
            plan=plan,
        )

        form = GoogleRecreateForm(
            {
                'user_id': user.id,
                'google_product_id': google_product_id,
                'purchase_token': purchase_token,
            }
        )

        self.assertFalse(form.is_valid())
        self.assertEqual(1, len(form.errors))
        self.assertIn('purchase_token', form.errors)


class PriceCardValidatorTest(TestCase):
    @responses.activate
    @mock.patch("amuse.tasks.zendesk_create_or_update_user")
    def setUp(self, _):
        self.country_us = CountryFactory(code='US', name='United State of America')
        self.country_uk = CountryFactory(code='UK', name='United Kingdom')
        self.country_ba = CountryFactory(code='BA', name='Bosnia and Herzegovina')

        self.plan = SubscriptionPlanFactory(
            countries=[self.country_us], create_card=False
        )

    def test_duplicate_price_cards_add(self):
        PriceCardFactory(countries=[self.country_us, self.country_uk], plan=self.plan)
        PriceCardFactory(countries=[self.country_ba], plan=self.plan)

        self.countries_list = [self.country_us, self.country_uk]

        with self.assertRaises(ValidationError):
            PriceCardValidator().validate_price_cards(self.plan, self.countries_list, 0)

    def test_duplicate_price_cards_change(self):
        PriceCardFactory(countries=[self.country_us, self.country_uk], plan=self.plan)
        self.price_card_for_change = PriceCardFactory(
            countries=[self.country_ba], plan=self.plan
        )

        self.countries_list = [self.country_us, self.country_uk]

        with self.assertRaises(ValidationError):
            PriceCardValidator().validate_price_cards(
                self.plan, self.countries_list, self.price_card_for_change.pk
            )

    def test_duplicate_introductory_price_cards_add(self):
        IntroductoryPriceCardFactory(
            countries=[self.country_us, self.country_uk], plan=self.plan
        )
        IntroductoryPriceCardFactory(countries=[self.country_ba], plan=self.plan)

        self.countries_list = [self.country_us, self.country_uk]

        with self.assertRaises(ValidationError):
            PriceCardValidator().validate_introductory_price_cards(
                self.plan, self.countries_list, 0
            )

    def test_duplicate_introductory_price_cards_change(self):
        IntroductoryPriceCardFactory(
            countries=[self.country_us, self.country_uk], plan=self.plan
        )
        self.price_card_for_change = IntroductoryPriceCardFactory(
            countries=[self.country_ba], plan=self.plan
        )

        self.countries_list = [self.country_us, self.country_uk]

        with self.assertRaises(ValidationError):
            PriceCardValidator().validate_introductory_price_cards(
                self.plan, self.countries_list, self.price_card_for_change.pk
            )


class PriceCardAdminFormTest(TestCase):
    @responses.activate
    @mock.patch("amuse.tasks.zendesk_create_or_update_user")
    def setUp(self, _):
        self.country_us = CountryFactory(code='US', name='United State of America')
        self.country_uk = CountryFactory(code='UK', name='United Kingdom')
        self.country_ba = CountryFactory(code='BA', name='Bosnia and Herzegovina')

        self.currency_usd = CurrencyFactory(code='USD')

        self.plan = SubscriptionPlanFactory(
            countries=[self.country_us], create_card=False
        )

    def test_price_card_form_not_valid(self):
        PriceCardFactory(countries=[self.country_us, self.country_uk], plan=self.plan)
        self.countries_list = [self.country_us, self.country_uk]

        form = PriceCardAdminForm(
            data={
                'plan': self.plan.id,
                'countries': self.countries_list,
                'price': 10,
                'currency': self.currency_usd,
            }
        )

        self.assertFalse(
            form.is_valid(),
            'Form should not be valid because we are trying to add price card with plan-country combination which already exist',
        )


class IntroductoryPriceCardAdminFormTest(TestCase):
    @responses.activate
    @mock.patch("amuse.tasks.zendesk_create_or_update_user")
    def setUp(self, _):
        self.country_us = CountryFactory(code='US', name='United State of America')
        self.country_uk = CountryFactory(code='UK', name='United Kingdom')
        self.country_ba = CountryFactory(code='BA', name='Bosnia and Herzegovina')

        self.currency_usd = CurrencyFactory(code='USD')

        self.plan = SubscriptionPlanFactory(
            countries=[self.country_us], create_card=False
        )

    def test_introductory_price_card_form_not_valid(self):
        IntroductoryPriceCardFactory(
            countries=[self.country_us, self.country_uk], plan=self.plan
        )
        self.countries_list = [self.country_us, self.country_uk]

        form = IntroductoryPriceCardAdminForm(
            data={
                'plan': self.plan.id,
                'countries': self.countries_list,
                'price': 10,
                'currency': self.currency_usd,
            }
        )

        self.assertFalse(
            form.is_valid(),
            'Form should not be valid because we are trying to add introductory price card with plan-country combination which already exist',
        )
