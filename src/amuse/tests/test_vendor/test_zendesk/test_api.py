import datetime
import json
from unittest import mock

import pytz
import responses
from django.test import override_settings
from flaky import flaky
from rest_framework.test import APITestCase
from unittest.mock import patch

from amuse.tests.helpers import (
    ZENDESK_MOCK_API_URL_TOKEN,
    zendesk_mock_show_job_status_response,
    zendesk_mock_create_many_tickets_response,
    zendesk_mock_create_many_tickets_request,
)
from amuse.vendor.zendesk.api import (
    create_or_update_user,
    update_users,
    create_ticket,
    bulk_create_users,
    show_job_status,
    create_tickets,
    delete_ticket,
    permanently_delete_user,
    get_zendesk_tickets_by_user,
    search_zendesk_users_by_email,
)
from payments.tests.factories import SubscriptionFactory
from subscriptions.models import SubscriptionPlan
from subscriptions.tests.factories import SubscriptionPlanFactory
from users.models import User


@override_settings(**ZENDESK_MOCK_API_URL_TOKEN)
class ZendeskIntegrationTestCase(APITestCase):
    @flaky(max_runs=3)
    @responses.activate
    @patch('amuse.tasks.zendesk_create_or_update_user')
    def test_create_or_update_pro_user(self, _):
        user = User()
        user.id = 12412

        # Initial save to populate `created` field that otherwise will be overwritten.
        user.save()

        user.first_name = 'Zoe'
        user.last_name = 'Zendeskable'
        user.email = 'zoe.zendeskable@amuse.io'
        user.phone = '+467601234567'
        user.artist_name = 'Dangerfield'
        user.created = datetime.datetime(2017, 3, 6, 16, 32, tzinfo=pytz.UTC)
        user.profile_link = 'http://my-artist-profile.com'
        user.category = User.CATEGORY_QUALIFIED
        user.save()

        # make User a PRO User
        SubscriptionFactory(user=user, valid_from=user.created)

        expected_zendesk_user_id = 8_912_198_629
        responses.add(
            responses.POST,
            'https://zendesk-mock-host/api/v2/users/create_or_update.json',
            status=201,
            json={'user': {'id': expected_zendesk_user_id}},
        )

        create_or_update_user(user.id)

        self.assertEqual(len(responses.calls), 1)
        self.assertEqual(
            responses.calls[0].request.url,
            'https://zendesk-mock-host/api/v2/users/create_or_update.json',
        )
        self.assertEqual(
            json.loads(responses.calls[0].request.body),
            {
                'user': {
                    'name': 'Zoe Zendeskable',
                    'email': 'zoe.zendeskable@amuse.io',
                    'external_id': 12412,
                    'phone': '+467601234567',
                    'user_fields': {
                        'subscription': 'pro',
                        'artist_name': 'Dangerfield',
                        'jarvi5_email': 'zoe.zendeskable@amuse.io',
                        'facebook_scoped': 'http://my-artist-profile.com',
                        'date_registered': '2017-03-06 16:32:00+00:00',
                        'releases': 0,
                        'fuga_migration': False,
                        'comment': '',
                        'user_category': 'Qualified',
                        'is_active': True,
                        'is_frozen': False,
                    },
                }
            },
        )

        user_updated = User.objects.get(pk=12412)
        self.assertEqual(user_updated.zendesk_id, expected_zendesk_user_id)

    @flaky(max_runs=3)
    @responses.activate
    @patch('amuse.tasks.zendesk_create_or_update_user')
    def test_create_or_update_plus_user(self, _):
        user = User()
        user.id = 12412

        # Initial save to populate `created` field that otherwise will be overwritten.
        user.save()

        user.first_name = 'Zoe'
        user.last_name = 'Zendeskable'
        user.email = 'zoe.zendeskable@amuse.io'
        user.phone = '+467601234567'
        user.artist_name = 'Dangerfield'
        user.created = datetime.datetime(2017, 3, 6, 16, 32, tzinfo=pytz.UTC)
        user.profile_link = 'http://my-artist-profile.com'
        user.category = User.CATEGORY_QUALIFIED
        user.save()

        # make User a PLUS / BOOST User
        plan = SubscriptionPlanFactory(tier=SubscriptionPlan.TIER_PLUS)
        SubscriptionFactory(user=user, valid_from=user.created, plan=plan)
        expected_zendesk_user_id = 8_912_198_629

        responses.add(
            responses.POST,
            'https://zendesk-mock-host/api/v2/users/create_or_update.json',
            status=201,
            json={'user': {'id': expected_zendesk_user_id}},
        )

        create_or_update_user(user.id)

        self.assertEqual(len(responses.calls), 1)
        self.assertEqual(
            responses.calls[0].request.url,
            'https://zendesk-mock-host/api/v2/users/create_or_update.json',
        )
        self.assertEqual(
            json.loads(responses.calls[0].request.body),
            {
                'user': {
                    'name': 'Zoe Zendeskable',
                    'email': 'zoe.zendeskable@amuse.io',
                    'external_id': 12412,
                    'phone': '+467601234567',
                    'user_fields': {
                        'subscription': 'boost',
                        'artist_name': 'Dangerfield',
                        'jarvi5_email': 'zoe.zendeskable@amuse.io',
                        'facebook_scoped': 'http://my-artist-profile.com',
                        'date_registered': '2017-03-06 16:32:00+00:00',
                        'releases': 0,
                        'fuga_migration': False,
                        'comment': '',
                        'user_category': 'Qualified',
                        'is_active': True,
                        'is_frozen': False,
                    },
                }
            },
        )

        user_updated = User.objects.get(pk=12412)
        self.assertEqual(user_updated.zendesk_id, expected_zendesk_user_id)

    @flaky(max_runs=3)
    @responses.activate
    @patch('amuse.tasks.zendesk_create_or_update_user')
    def test_create_or_update_free_user(self, _):
        user = User()
        user.id = 12412

        # Initial save to populate `created` field that otherwise will be overwritten.
        user.save()

        user.first_name = 'Zoe'
        user.last_name = 'Zendeskable'
        user.email = 'zoe.zendeskable@amuse.io'
        user.phone = '+467601234567'
        user.artist_name = 'Dangerfield'
        user.created = datetime.datetime(2017, 3, 6, 16, 32, tzinfo=pytz.UTC)
        user.profile_link = 'http://my-artist-profile.com'
        user.category = User.CATEGORY_QUALIFIED
        user.save()

        expected_zendesk_user_id = 8_912_198_629
        responses.add(
            responses.POST,
            'https://zendesk-mock-host/api/v2/users/create_or_update.json',
            status=201,
            json={'user': {'id': 8_912_198_629}},
        )

        create_or_update_user(user.id)

        self.assertEqual(len(responses.calls), 1)
        self.assertEqual(
            responses.calls[0].request.url,
            'https://zendesk-mock-host/api/v2/users/create_or_update.json',
        )
        self.assertEqual(
            json.loads(responses.calls[0].request.body),
            {
                'user': {
                    'name': 'Zoe Zendeskable',
                    'email': 'zoe.zendeskable@amuse.io',
                    'external_id': 12412,
                    'phone': '+467601234567',
                    'user_fields': {
                        'subscription': 'free',
                        'artist_name': 'Dangerfield',
                        'jarvi5_email': 'zoe.zendeskable@amuse.io',
                        'facebook_scoped': 'http://my-artist-profile.com',
                        'date_registered': '2017-03-06 16:32:00+00:00',
                        'releases': 0,
                        'fuga_migration': False,
                        'comment': '',
                        'user_category': 'Qualified',
                        'is_active': True,
                        'is_frozen': False,
                    },
                }
            },
        )

        user_updated = User.objects.get(pk=12412)
        self.assertEqual(user_updated.zendesk_id, expected_zendesk_user_id)

    @responses.activate
    @override_settings(**ZENDESK_MOCK_API_URL_TOKEN)
    def test_update_users(self):
        # Load users, not saving them in db
        users = []
        expected_to_update_ids = set()
        with open(
            "amuse/tests/test_vendor/test_zendesk/test_data/users.json", "r"
        ) as f:
            for u in json.load(f):
                user = User()
                for k, v in u.items():
                    setattr(user, k, v)
                users.append(user)

                if user.zendesk_id:
                    expected_to_update_ids.add(user.id)

        responses.add(
            responses.PUT,
            'https://zendesk-mock-host/api/v2/users/update_many.json',
            status=200,
        )
        update_users(users)
        updated_users = json.loads(responses.calls[0].request.body)["users"]

        # Check that only existing zendesk users were updated
        self.assertEqual(len(expected_to_update_ids), len(updated_users))
        for u in updated_users:
            self.assertIn(u["external_id"], expected_to_update_ids)

    @responses.activate
    @override_settings(**ZENDESK_MOCK_API_URL_TOKEN)
    def test_bulk_create_users(self):
        users_for_create = []
        expected_to_create_ids = set()
        with open(
            "amuse/tests/test_vendor/test_zendesk/test_data/users.json", "r"
        ) as f:
            for u in json.load(f):
                user = User()
                for k, v in u.items():
                    setattr(user, k, v)
                if not user.zendesk_id:
                    users_for_create.append(user)
                    expected_to_create_ids.add(user.id)

        responses.add(
            responses.POST,
            'https://zendesk-mock-host/api/v2/users/create_or_update_many.json',
            status=200,
        )

        bulk_create_users(users_for_create)
        created_users = json.loads(responses.calls[0].request.body)["users"]
        self.assertEqual(len(users_for_create), len(created_users))
        for u in created_users:
            self.assertIn(u["external_id"], expected_to_create_ids)

    @responses.activate
    @override_settings(**ZENDESK_MOCK_API_URL_TOKEN)
    def test_show_job_status(self):
        mock_zendesk_host = "zendesk-mock-host"
        job_id = "8b726e606741012ffc2d782bcb7848fe"
        responses.add(
            responses.GET,
            f'https://{mock_zendesk_host}/api/v2/job_statuses/{job_id}.json',
            status=200,
            json=zendesk_mock_show_job_status_response(mock_zendesk_host, job_id),
        )
        show_job_status(job_id)

        self.assertEqual(len(responses.calls), 1)

    @responses.activate
    @override_settings(**ZENDESK_MOCK_API_URL_TOKEN)
    def test_create_tickets(self):
        mock_zendesk_host = "zendesk-mock-host"
        job_id = "8b726e606741012ffc2d782bcb7848fe"
        responses.add(
            responses.POST,
            f'https://{mock_zendesk_host}/api/v2/tickets/create_many',
            status=200,
            json=zendesk_mock_create_many_tickets_response(mock_zendesk_host, job_id),
        )

        create_tickets(zendesk_mock_create_many_tickets_request())

        self.assertEqual(len(responses.calls), 1)

    @responses.activate
    @override_settings(**ZENDESK_MOCK_API_URL_TOKEN)
    @mock.patch("amuse.vendor.zendesk.api.logger.info")
    def test_create_ticket(self, mock_logger_info):
        user_id = 1234
        data = {
            "subject": "Amuse Account Delete Request",
            "comment": "This ticket is created because user requested account delete",
            "type": "task",
        }

        responses.add(
            responses.POST, 'https://zendesk-mock-host/api/v2/tickets', status=201
        )
        create_ticket(user_id, data)

        self.assertEqual(len(responses.calls), 1)
        request_ticket = json.loads(responses.calls[0].request.body)["ticket"]
        self.assertEqual(request_ticket.get("subject"), data.get("subject"))
        self.assertEqual(request_ticket.get("type"), data.get("type"))
        self.assertEqual(
            request_ticket.get("comment"),
            {"body": data.get("comment"), "public": False},
        )

        mock_payload = {
            "ticket": {
                "subject": data["subject"],
                "comment": {"body": data["comment"], "public": False},
                "type": data["type"],
            }
        }
        mock_logger_info.assert_called_once_with(
            f'Creating Zendesk ticket with following payload: {mock_payload}'
        )

    @responses.activate
    @override_settings(**ZENDESK_MOCK_API_URL_TOKEN)
    @mock.patch("amuse.vendor.zendesk.api.logger.warning")
    def test_create_ticket_fail(self, mock_logger_warning):
        user_id = 1234
        data = {
            "subject": "Amuse Account Delete Request",
            "comment": "This ticket is created because user requested account delete",
            "type": "task",
        }

        responses.add(
            responses.POST, 'https://zendesk-mock-host/api/v2/tickets', status=400
        )

        create_ticket(user_id, data)

        mock_logger_warning.assert_called_once_with(
            f'HTTP error occurred while creating zendesk ticket. User_id {user_id}: 400 Client Error: Bad Request for url: https://zendesk-mock-host/api/v2/tickets'
        )

    @responses.activate
    @override_settings(**ZENDESK_MOCK_API_URL_TOKEN)
    def test_delete_ticket(self):
        mock_zendesk_host = "zendesk-mock-host"
        ticket_id = "1323123123123"
        responses.add(
            responses.DELETE,
            f'https://{mock_zendesk_host}/api/v2/tickets/{ticket_id}',
            status=204,
        )
        delete_ticket(ticket_id)

        self.assertEqual(len(responses.calls), 1)

    @responses.activate
    @override_settings(**ZENDESK_MOCK_API_URL_TOKEN)
    def test_delete_user(self):
        mock_zendesk_host = "zendesk-mock-host"
        user_id = "1323123123123"
        responses.add(
            responses.DELETE,
            f'https://{mock_zendesk_host}/api/v2/users/{user_id}',
            status=204,
        )
        responses.add(
            responses.DELETE,
            f'https://{mock_zendesk_host}/api/v2/deleted_users/{user_id}',
            status=204,
        )
        permanently_delete_user(user_id)

        self.assertEqual(len(responses.calls), 2)

    @responses.activate
    @override_settings(**ZENDESK_MOCK_API_URL_TOKEN)
    def test_get_zendesk_tickets_by_user(self):
        mock_zendesk_host = "zendesk-mock-host"
        user_id = "1323123123123"
        responses.add(
            responses.GET,
            f'https://{mock_zendesk_host}/api/v2/users/{user_id}/tickets/requested',
            status=200,
            json={},
        )
        get_zendesk_tickets_by_user(user_id)

        self.assertEqual(len(responses.calls), 1)

    @responses.activate
    @override_settings(**ZENDESK_MOCK_API_URL_TOKEN)
    def test_search_zendesk_users_by_email(self):
        mock_zendesk_host = "zendesk-mock-host"
        email = "test_email@isp.com"
        responses.add(
            responses.GET,
            f'https://{mock_zendesk_host}/api/v2/users/search.json?query=email:"{email}"',
            status=200,
            json={},
        )
        search_zendesk_users_by_email(email)

        self.assertEqual(len(responses.calls), 1)
