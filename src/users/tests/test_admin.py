from unittest import mock

import responses
from dateutil.relativedelta import relativedelta
from django.contrib.admin import site
from django.contrib.admin.sites import AdminSite
from django.test import RequestFactory, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from amuse.tests.helpers import (
    ZENDESK_MOCK_API_URL_TOKEN,
    add_zendesk_mock_post_response,
)
from payments.tests.factories import PaymentTransactionFactory
from subscriptions.tests.factories import SubscriptionFactory, SubscriptionPlanFactory
from users.admin import UserAdmin, UserForm, ArtistV2Admin
from users.models import User, ArtistV2
from users.tests.factories import UserFactory, Artistv2Factory


@override_settings(**ZENDESK_MOCK_API_URL_TOKEN)
class UserAdminUserFrozenCase(TestCase):
    @responses.activate
    def setUp(self):
        add_zendesk_mock_post_response()
        site = AdminSite()

        self.admin = UserAdmin(model=User, admin_site=site)
        self.request = RequestFactory().get('/admin')
        self.request.user = UserFactory(is_staff=True)

        self.user = UserFactory(is_frozen=False, email='test@email.com')
        self.plan = SubscriptionPlanFactory()
        self.sub = SubscriptionFactory(user=self.user, plan=self.plan)
        self.payment = PaymentTransactionFactory(subscription=self.sub, user=self.user)
        self.payment.created = timezone.now() - relativedelta(days=1)
        self.payment.paid_until = self.payment.created + relativedelta(months=1)
        self.payment.save()
        self.payment.refresh_from_db()

    @responses.activate
    @mock.patch('users.admin.user_frozen')
    def test_subbscription_canceled(self, user_frozen_mock):
        add_zendesk_mock_post_response()

        # make sure setup is OK
        self.assertTrue(self.user.is_pro)
        self.assertIsNone(self.sub.valid_until)

        # make changes in admin
        form = UserForm()
        form.instance.id = self.user.id
        form.changed_data = ['is_frozen']
        self.user.is_frozen = True

        self.admin.save_model(self.request, self.user, form, True)

        self.sub.refresh_from_db()
        self.assertEqual(1, user_frozen_mock.call_count)
        self.assertIsNotNone(self.sub.valid_until)
        self.assertEqual(self.sub.valid_until, self.payment.paid_until.date())

    @responses.activate
    def test_user_subscription_link(self):
        add_zendesk_mock_post_response()
        encoded_email = 'test%40email.com'
        expected = f'<a href="/admin/subscriptions/subscription/?q={encoded_email}">1 Subscriptions</a>'
        result = self.admin.subscription_link(self.user)
        self.assertEqual(result, expected)


class UserAdminActionTestCase(TestCase):
    @responses.activate
    @mock.patch("amuse.tasks.zendesk_create_or_update_user")
    def setUp(self, mock_zendesk):
        admin_user = UserFactory(is_staff=True, category=User.CATEGORY_DEFAULT)
        self.user_1 = UserFactory()
        self.user_2 = UserFactory()
        self.user_3 = UserFactory()

        self.client.force_login(user=admin_user)

        self.original_password_1 = self.user_1.password
        self.original_token_1 = self.user_1.auth_token
        self.original_password_2 = self.user_2.password
        self.original_token_2 = self.user_2.auth_token
        self.original_password_3 = self.user_3.password
        self.original_token_3 = self.user_3.auth_token

    @mock.patch("users.admin.send_password_reset")
    def test_reset_password_and_rotate_token(self, mock_send_email):
        change_url = reverse("admin:users_user_changelist")
        data = {
            "action": "reset_passwords_and_rotate_tokens",
            '_selected_action': [self.user_1.pk, self.user_3.pk],
        }
        response = self.client.post(change_url, data, follow=True)

        self.user_1.refresh_from_db()
        self.user_2.refresh_from_db()
        self.user_3.refresh_from_db()

        assert self.original_password_1 != self.user_1.password
        assert self.original_token_1 != self.user_1.auth_token

        assert self.original_password_2 == self.user_2.password
        assert self.original_token_2 == self.user_2.auth_token

        assert self.original_password_3 != self.user_3.password
        assert self.original_token_3 != self.user_3.auth_token

        assert self.user_1.auth_token != self.user_3.auth_token

        assert mock_send_email.mock_calls == [
            mock.call(self.user_3, urlconf="amuse.urls.app"),
            mock.call(self.user_1, urlconf="amuse.urls.app"),
        ]


class ArtistV2AdminTestCase(TestCase):
    @responses.activate
    @mock.patch("amuse.tasks.zendesk_create_or_update_user")
    def setUp(self, mock_zendesk):
        self.artist_first = Artistv2Factory.create(id=1337)
        self.artist_seconds = Artistv2Factory.create(id=1338)
        self.request_factory = RequestFactory()
        self.admin_user = UserFactory(is_staff=True, category=User.CATEGORY_DEFAULT)
        self.client.force_login(user=self.admin_user)

    def sort_results(self, results):
        return sorted(results, key=lambda res: res.id)

    def test_filter_users_using_multipe_ids(self):
        modeladmin = ArtistV2Admin(ArtistV2, site)

        request = self.request_factory.get('/', {'artist': '1337,1338'})
        request.user = self.admin_user

        changelist = modeladmin.get_changelist_instance(request)
        queryset = changelist.get_queryset(request)

        result = self.sort_results(list(queryset))
        expected = self.sort_results([self.artist_first, self.artist_seconds])

        self.assertEqual(result, expected)

    def test_filter_users_using_empty_string(self):
        modeladmin = ArtistV2Admin(ArtistV2, site)

        request = self.request_factory.get('/', {'artist': ''})
        request.user = self.admin_user
        changelist = modeladmin.get_changelist_instance(request)
        queryset = changelist.get_queryset(request)

        result = self.sort_results(list(queryset))
        expected = self.sort_results([self.artist_first, self.artist_seconds])

        self.assertEqual(result, expected)

    def test_delete_action_removed(self):
        modeladmin = ArtistV2Admin(ArtistV2, site)
        request = self.request_factory.get('/', {'artist': ''})
        request.user = self.admin_user
        actions = modeladmin.get_actions(request)
        assert 'delete_selected' not in list(actions.keys())

    def test_delete_action_removed_user(self):
        modeladmin = ArtistV2Admin(User, site)
        request = self.request_factory.get('/', {'user': ''})
        request.user = self.admin_user
        actions = modeladmin.get_actions(request)
        assert 'delete_selected' not in list(actions.keys())

    def test_filter_users_using_single_id(self):
        modeladmin = ArtistV2Admin(ArtistV2, site)

        request = self.request_factory.get('/', {'artist': '1337'})
        request.user = self.admin_user
        changelist = modeladmin.get_changelist_instance(request)
        queryset = changelist.get_queryset(request)

        result = list(queryset)
        expected = [self.artist_first]

        self.assertEqual(result, expected)

    def test_filter_users_using_not_existing_id(self):
        modeladmin = ArtistV2Admin(ArtistV2, site)

        request = self.request_factory.get('/', {'artist': '5432'})
        request.user = self.admin_user
        changelist = modeladmin.get_changelist_instance(request)
        queryset = changelist.get_queryset(request)

        result = list(queryset)
        expected = []

        self.assertEqual(result, expected)

    def test_filter_users_using_multipe_ids_one_does_not_exist(self):
        modeladmin = ArtistV2Admin(ArtistV2, site)

        request = self.request_factory.get('/', {'artist': '1337,1338,5432'})
        request.user = self.admin_user

        changelist = modeladmin.get_changelist_instance(request)
        queryset = changelist.get_queryset(request)

        result = self.sort_results(list(queryset))
        expected = self.sort_results([self.artist_first, self.artist_seconds])

        self.assertEqual(result, expected)

    def test_filter_users_using_multipe_random_string(self):
        modeladmin = ArtistV2Admin(ArtistV2, site)

        request = self.request_factory.get('/', {'artist': 'this should not be done'})
        request.user = self.admin_user

        changelist = modeladmin.get_changelist_instance(request)
        queryset = changelist.get_queryset(request)

        result = list(queryset)
        expected = []

        self.assertEqual(result, expected)


class UserAdminBulkEditActionTestCase(TestCase):
    @responses.activate
    @mock.patch("amuse.tasks.zendesk_create_or_update_user")
    def setUp(self, mock_zendesk):
        admin_user = UserFactory(is_staff=True, category=User.CATEGORY_DEFAULT)
        self.user_1 = UserFactory()
        self.user_2 = UserFactory()
        self.user_3 = UserFactory()

        self.client.force_login(user=admin_user)

    @mock.patch("django.db.models.signals.ModelSignal.send")
    def test_bulk_edit_get(self, _):
        change_url = reverse("admin:users_user_changelist")
        data = {
            "action": "bulk_edit",
            '_selected_action': [self.user_1.pk, self.user_3.pk],
        }
        response = self.client.post(change_url, data, follow=True)

        self.assertEqual(200, response.status_code)

    @mock.patch("django.db.models.signals.ModelSignal.send")
    def test_bulk_edit_post(self, _):
        change_url = reverse("admin:users_user_changelist")
        data = {
            "post": "yes",
            "action": "bulk_edit",
            '_selected_action': [self.user_1.pk, self.user_3.pk],
            'step': '1',
            'category_0': 'on',
            'category_1': '1',
            'flagged_reason_0': 'on',
            'flagged_reason_1': '2',
        }
        response = self.client.post(change_url, data, follow=True)

        self.user_1.refresh_from_db()
        self.user_2.refresh_from_db()
        self.user_3.refresh_from_db()

        self.assertEqual(200, response.status_code)
        self.assertEqual(1, self.user_1.category)
        self.assertEqual(1, self.user_3.category)

    @override_settings(**{'BULK_EDIT_MAX_USERS': 2})
    @mock.patch("django.db.models.signals.ModelSignal.send")
    def test_bulk_edit_post_max_users(self, _):
        change_url = reverse("admin:users_user_changelist")
        data = {
            "action": "bulk_edit",
            '_selected_action': [self.user_1.pk, self.user_2.pk, self.user_3.pk],
        }
        response = self.client.post(change_url, data, follow=True)

        self.assertEqual(200, response.status_code)
        self.assertIn('messages', response.context)
        self.assertEqual(1, len(response.context['messages']))
        error_message = (
            'The maximum number of Users that can be edited with bulk edit action is 2'
        )
        self.assertEqual(error_message, str(list(response.context['messages'])[0]))
