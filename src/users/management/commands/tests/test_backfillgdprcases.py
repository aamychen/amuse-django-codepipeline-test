from unittest import mock

from django.core.management import call_command
from django.test import TestCase

from users.tests.factories import UserFactory, UserMetadataFactory, UserGDPRFactory


class TestBackfillGDPRCasesTestCase(TestCase):
    def setUp(self):
        with mock.patch("amuse.tasks.zendesk_create_or_update_user"):
            self.user1 = UserFactory()  # wiped, metadata
            self.user2 = UserFactory()  # wiped, no metadata
            self.user3 = UserFactory()  # not wiped
            self.metadata = UserMetadataFactory(user=self.user1)

            self.gdpr1 = UserGDPRFactory(
                user=self.user1,
                minfraud_entries=True,
                artist_v2_history_entries=True,
                user_history_entries=True,
                email_adress=True,
                user_first_name=True,
                user_last_name=True,
                user_social_links=True,
                user_artist_name=True,
                artist_v2_names=True,
                artist_v2_social_links=True,
                artist_v1_names=True,
                artist_v1_social_links=True,
                user_apple_signin_id=True,
                user_facebook_id=True,
                user_firebase_token=True,
                user_zendesk_id=True,
                transaction_withdrawals=True,
                user_isactive_deactivation=True,
                user_newsletter_deactivation=True,
            )
            self.gdpr2 = UserGDPRFactory(
                user=self.user2,
                minfraud_entries=True,
                artist_v2_history_entries=True,
                user_history_entries=True,
                email_adress=True,
                user_first_name=True,
                user_last_name=True,
                user_social_links=True,
                user_artist_name=True,
                artist_v2_names=True,
                artist_v2_social_links=True,
                artist_v1_names=True,
                artist_v1_social_links=True,
                user_apple_signin_id=True,
                user_facebook_id=True,
                user_firebase_token=True,
                user_zendesk_id=True,
                transaction_withdrawals=True,
                user_isactive_deactivation=True,
                user_newsletter_deactivation=True,
            )

    def test_gdpr_cases_metadata_is_backfilled(self):
        self.assertFalse(self.user1.is_gdpr_wiped)
        self.assertFalse(self.user2.is_gdpr_wiped)
        self.assertFalse(self.user3.is_gdpr_wiped)

        call_command('backfillgdprcases')

        self.user1.refresh_from_db()
        self.user2.refresh_from_db()
        self.user3.refresh_from_db()
        self.assertTrue(self.user1.is_gdpr_wiped)
        self.assertTrue(self.user2.is_gdpr_wiped)
        self.assertFalse(self.user3.is_gdpr_wiped)

    def test_incomplete_wipes_are_ignored(self):
        self.gdpr1.minfraud_entries = False
        self.gdpr1.save()

        call_command('backfillgdprcases')

        self.user1.refresh_from_db()
        self.assertFalse(self.user1.is_gdpr_wiped)
