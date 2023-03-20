from django.test import TestCase
from datetime import datetime, timedelta
from unittest.mock import patch

from users.models import ArtistV2
from users.tests.factories import Artistv2Factory, TeamInvitationFactory
from releases.tests.factories import SongArtistRoleFactory, ReleaseArtistRoleFactory
from users.artistv2_cleanup import delete_orphan_artistv2


class TestArtistV2Cleanup(TestCase):
    def create_artistv2_orphans(self):
        a1 = Artistv2Factory(name="orphan1", owner=None)
        a2 = Artistv2Factory(name="orphan2", owner=None)
        a3 = Artistv2Factory(name="orphan3", owner=None)
        a4 = Artistv2Factory(name="orphan4", owner=None)

        a1.created = datetime.now() - timedelta(days=31)
        a1.save()

        a2.created = datetime.now() - timedelta(days=31)
        a2.save()

        a3.created = datetime.now() - timedelta(days=31)
        a3.save()

    def create_referenced_artistv2(self):
        Artistv2Factory(name="ArtistWithOwner")
        referenced_artist = Artistv2Factory(name="Referenced", owner=None)
        referenced_artist2 = Artistv2Factory(name="Referenced2", owner=None)
        referenced_artist3 = Artistv2Factory(name="Invited", owner=None)
        ReleaseArtistRoleFactory(artist=referenced_artist)
        SongArtistRoleFactory(artist=referenced_artist2)
        TeamInvitationFactory(artist=referenced_artist3)

    @patch('amuse.tasks.zendesk_create_or_update_user')
    def test_orphan_cleanup(self, mock_zendesk):
        self.create_artistv2_orphans()
        self.create_referenced_artistv2()
        deleted = delete_orphan_artistv2(is_test=True)
        # Assert only orphans are deleted
        self.assertEqual(deleted, 3)
        self.assertEqual(ArtistV2.objects.filter(name="ArtistWithOwner").count(), 1)
        self.assertEqual(ArtistV2.objects.filter(name="Referenced").count(), 1)
        self.assertEqual(ArtistV2.objects.filter(name="Referenced2").count(), 1)
        self.assertEqual(ArtistV2.objects.filter(name="Invited").count(), 1)
        self.assertEqual(ArtistV2.objects.filter(name="orphan1").count(), 0)
        self.assertEqual(ArtistV2.objects.filter(name="orphan2").count(), 0)
        self.assertEqual(ArtistV2.objects.filter(name="orphan3").count(), 0)
        self.assertEqual(ArtistV2.objects.filter(name="orphan4").count(), 1)
