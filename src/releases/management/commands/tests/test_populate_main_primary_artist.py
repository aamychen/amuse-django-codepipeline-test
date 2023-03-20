from io import StringIO
from unittest import mock
from django.core.management import call_command
from django.test import TestCase
from releases.models import ReleaseArtistRole
from releases.tests.factories import ReleaseFactory, ReleaseArtistRoleFactory


class BackfillRARTestCase(TestCase):
    @mock.patch("amuse.tasks.zendesk_create_or_update_user")
    def setUp(self, mocked_zendesk):
        self.release1 = ReleaseFactory()  # rar data correct
        self.rar1 = ReleaseArtistRoleFactory(
            release=self.release1, main_primary_artist=True
        )
        self.rar2 = ReleaseArtistRoleFactory(
            release=self.release1, main_primary_artist=False
        )

        self.release2 = ReleaseFactory()  # rar missing main_primary_artist
        self.rar3 = ReleaseArtistRoleFactory(
            release=self.release2, main_primary_artist=False
        )
        self.rar4 = ReleaseArtistRoleFactory(
            release=self.release2, main_primary_artist=False
        )
        self.rar5 = ReleaseArtistRoleFactory(
            release=self.release2,
            role=ReleaseArtistRole.ROLE_FEATURED_ARTIST,
            main_primary_artist=False,
        )

        self.release3 = ReleaseFactory()  # rar missing entirely

        self.release4 = ReleaseFactory()  # PRIMARY is created after Featured
        self.rar6 = ReleaseArtistRoleFactory(
            role=ReleaseArtistRole.ROLE_FEATURED_ARTIST,
            release=self.release4,
            main_primary_artist=False,
        )
        self.rar7 = ReleaseArtistRoleFactory(release=self.release4)

    def test_run(self):
        out = StringIO()
        call_command('populate_main_primary_artist', stdout=out)

        self.rar1.refresh_from_db()
        self.assertTrue(self.rar1.main_primary_artist)

        self.rar2.refresh_from_db()
        self.assertFalse(self.rar2.main_primary_artist)

        self.rar3.refresh_from_db()
        self.assertTrue(self.rar3.main_primary_artist)

        self.rar4.refresh_from_db()
        self.assertFalse(self.rar4.main_primary_artist)

        self.assertFalse(self.release3.releaseartistrole_set.exists())

        self.rar6.refresh_from_db()
        self.assertFalse(self.rar6.main_primary_artist)

        self.rar7.refresh_from_db()
        self.assertTrue(self.rar7.main_primary_artist)
