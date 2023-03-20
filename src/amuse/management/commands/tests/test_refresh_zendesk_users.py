import responses
from unittest import mock
from django.core.management import call_command
from django.test import TestCase, override_settings
from amuse.tests.helpers import (
    add_zendesk_mock_post_response,
    ZENDESK_MOCK_API_URL_TOKEN,
)
from users.tests.factories import UserFactory


@override_settings(**ZENDESK_MOCK_API_URL_TOKEN)
@override_settings(CELERY_TASK_SERIALIZER="pickle")
class RefreshZendeskUsersTestCase(TestCase):
    class MockedResponse:
        def __init__(self, status_code=200):
            self.status_code = status_code

        def raise_for_status(self):
            pass

    processed_zendesk_users = 0

    @responses.activate
    def test_update_users(self):
        def update_users_side_effect(*args):
            # Counts the total amount of users processed by the mocked method
            zendesk_users = args[0]
            self.processed_zendesk_users += len(zendesk_users)
            return RefreshZendeskUsersTestCase.MockedResponse()

        expected_processed_zen_users = 19
        total_users = 22

        add_zendesk_mock_post_response()

        # Generate test users
        users = UserFactory.create_batch(total_users)
        for i, user in enumerate(users):
            if i == expected_processed_zen_users:
                break
            user.zendesk_id = i + 1
            user.save()

        with mock.patch(
            'amuse.vendor.zendesk.api.update_users'
        ) as mock_update_users, mock.patch(
            'amuse.management.commands.refresh_zendesk_users.Command.INTERVAL_SECONDS',
            0.0,
        ):
            mock_update_users.side_effect = update_users_side_effect
            call_command('refresh_zendesk_users', batchsize=10)

            self.assertEqual(mock_update_users.call_count, 2)
            self.assertEqual(self.processed_zendesk_users, expected_processed_zen_users)
