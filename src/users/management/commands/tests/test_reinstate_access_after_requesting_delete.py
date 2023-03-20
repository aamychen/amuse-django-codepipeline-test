import responses
from rest_framework.authtoken.models import Token
from django.core.management import call_command
from django.test import TestCase, override_settings

from amuse.tests.helpers import (
    ZENDESK_MOCK_API_URL_TOKEN,
    add_zendesk_mock_post_response,
)
from users.tests.factories import UserFactory, UserMetadataFactory


@override_settings(**ZENDESK_MOCK_API_URL_TOKEN)
class ReinstateAccessAfterRequestingAccountDelete(TestCase):
    @responses.activate
    def setUp(self):
        add_zendesk_mock_post_response()
        self.user = UserFactory()
        self.user_metadata = UserMetadataFactory(user=self.user)

    def test_command_success(self):
        # Remove token and flag for delete
        token = Token.objects.filter(user__id=self.user.id)
        token.delete()
        self.user.flag_for_delete()

        self.user.refresh_from_db()

        call_command(
            'reinstate_access_after_requesting_delete', f"--user-id={self.user.id}"
        )

        self.user.refresh_from_db()
        self.assertIsNotNone(self.user.auth_token)
        self.assertIsNotNone(self.user.auth_token.key)
        self.assertFalse(self.user.usermetadata.is_delete_requested)
        self.assertIsNone(self.user.usermetadata.delete_requested_at)

    def test_command_dry_run(self):
        # Remove token and flag for delete
        token = Token.objects.filter(user__id=self.user.id)
        token.delete()
        self.user.flag_for_delete()

        self.user.refresh_from_db()

        call_command(
            'reinstate_access_after_requesting_delete',
            f"--user-id={self.user.id}",
            "--dry-run",
        )

        self.user.refresh_from_db()
        self.assertFalse(hasattr(self.user, 'auth_token'))
        self.assertTrue(self.user.usermetadata.is_delete_requested)
        self.assertIsNotNone(self.user.usermetadata.delete_requested_at)
