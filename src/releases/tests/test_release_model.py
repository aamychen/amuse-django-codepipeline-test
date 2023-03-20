from unittest.mock import patch

from django.test import TestCase
from simple_history.manager import HistoryManager

from codes.models import UPC
from codes.tests.factories import UPCFactory
from countries.tests.factories import CountryFactory
from releases.models import (
    Release,
    ReleaseArtistRole,
    ReleaseStoresHistory,
    SongArtistRole,
)
from releases.tests.factories import (
    ReleaseArtistRoleFactory,
    ReleaseFactory,
    SongFactory,
    SongArtistRoleFactory,
    StoreFactory,
)
from users.tests.factories import Artistv2Factory, UserFactory


class ReleaseTestCase(TestCase):
    RELEASE_WITH_LICENSE_INFO = {
        "release": {
            "id": "43256",
            "upc": "0611056503515",
            "name": "Hex",
            "version": "",
            "release_date": "2018-03-12T00:00:00Z",
            "artist_name": "80purppp",
            "user_id": "37561",
            "status": "RELEASED",
            "contributors": [
                {
                    "sequence": 1,
                    "role": "PRIMARY_ARTIST",
                    "artist_id": "104317",
                    "artist_name": "80purppp",
                    "artist_ownerId": "37561",
                    "main_primaryArtist": False,
                }
            ],
            "active_agreement_ids": ["2379f8aa-f1be-4906-a36f-05fc912bdd38"],
        }
    }
    RELEASE_WITHOUT_LICENSE_INFO = {
        "release": {
            "id": "43256",
            "upc": "0611056503515",
            "name": "Hex",
            "version": "",
            "release_date": "2018-03-12T00:00:00Z",
            "artist_name": "80purppp",
            "user_id": "37561",
            "status": "RELEASED",
            "contributors": [
                {
                    "sequence": 1,
                    "role": "PRIMARY_ARTIST",
                    "artist_id": "104317",
                    "artist_name": "80purppp",
                    "artist_ownerId": "37561",
                    "main_primaryArtist": False,
                }
            ],
        }
    }

    def setUp(self):
        self.statuses = [status for status, _ in Release.STATUS_CHOICES]
        self.not_approved_statuses = [
            status for status in self.statuses if status != Release.STATUS_APPROVED
        ]

    @patch(
        'releases.models.release.get_release_with_license_info',
        return_value=RELEASE_WITH_LICENSE_INFO,
    )
    def test_has_licensed_tracks(self, mocked_zendesk):
        release = ReleaseFactory()
        SongFactory(release=release)

        assert release.has_licensed_tracks is True

    @patch(
        'releases.models.release.get_release_with_license_info',
        return_value=RELEASE_WITHOUT_LICENSE_INFO,
    )
    def test_no_licensed_tracks(self, mocked_zendesk):
        release = ReleaseFactory()
        SongFactory(release=release)

        assert release.has_licensed_tracks is False

    @patch('releases.models.release.get_release_with_license_info', return_value={})
    def test_no_licensed_tracks_on_invalid_release_id(self, mocked_zendesk):
        release = ReleaseFactory()
        SongFactory(release=release)

        assert release.has_licensed_tracks is False

    @patch('amuse.tasks.zendesk_create_or_update_user')
    def test_has_invalid_artist_roles(self, mocked_zendesk):
        release = ReleaseFactory()
        song = SongFactory(release=release)
        artist = Artistv2Factory(owner=release.user)
        SongArtistRoleFactory(
            artist=artist, song=song, role=SongArtistRole.ROLE_PRIMARY_ARTIST
        )
        SongArtistRoleFactory(
            artist=artist, song=song, role=SongArtistRole.ROLE_FEATURED_ARTIST
        )

        assert release.has_invalid_artist_roles is True

    @patch('amuse.tasks.zendesk_create_or_update_user')
    def test_release_stores_history(self, mocked_zendesk):
        release = ReleaseFactory()
        store_1 = StoreFactory(name="first_change")
        store_2 = StoreFactory(name="second_change")

        release.stores.set([store_1, store_2])

        assert ReleaseStoresHistory.objects.last().stores.count() == 0

        release.stores.set([store_1])

        assert sorted(
            list(
                ReleaseStoresHistory.objects.last().stores.values_list(
                    "name", flat=True
                )
            )
        ) == [store_1.name, store_2.name]

        release.stores.set([])

        assert sorted(
            list(
                ReleaseStoresHistory.objects.last().stores.values_list(
                    "name", flat=True
                )
            )
        ) == [store_1.name]

    @patch('amuse.tasks.zendesk_create_or_update_user')
    def test_release_history(self, mocked_zendesk):
        """Release model history is enabled."""
        release = Release()
        self.assertTrue(isinstance(release.history, HistoryManager))
        self.assertEqual(release.history.count(), 0)

        release = ReleaseFactory()
        # 2 because https://github.com/FactoryBoy/factory_boy/issues/316
        self.assertEqual(release.history.count(), 2)

    @patch('amuse.tasks.zendesk_create_or_update_user')
    def test_release_doesnt_set_asap_release_date_while_changing_status_to_any_except_approved(
        self, mocked_zendesk
    ):
        release = ReleaseFactory(
            status=Release.STATUS_SUBMITTED,
            schedule_type=Release.SCHEDULE_TYPE_ASAP,
            release_date=None,
        )
        for status in self.not_approved_statuses:
            release.status = status
            release.save()
            self.assertIsNone(release.release_date)
        release.status = Release.STATUS_APPROVED
        release.save()
        self.assertIsNotNone(release.release_date)

    @patch('amuse.tasks.zendesk_create_or_update_user')
    def test_release_doesnt_update_static_release_date_(self, mocked_zendesk):
        release = ReleaseFactory(
            status=Release.STATUS_SUBMITTED, schedule_type=Release.SCHEDULE_TYPE_STATIC
        )
        release_date = release.release_date
        for status in self.statuses:
            release.status = status
            release.save()
            self.assertEqual(release.release_date, release_date)

    @patch('amuse.tasks.zendesk_create_or_update_user')
    def test_release_doesnt_get_upc_while_changing_status_to_any_except_approved(
        self, mocked_zendesk
    ):
        release = ReleaseFactory(status=Release.STATUS_SUBMITTED, upc=None)
        for status in self.not_approved_statuses:
            release.status = status
            release.save()
            self.assertIsNone(release.upc)

    @patch('amuse.tasks.zendesk_create_or_update_user')
    def test_created_approved_release_doesnt_change_upc_while_changing_status(
        self, mocked_zendesk
    ):
        upc = UPCFactory(status=UPC.STATUS_UNUSED)
        release = ReleaseFactory(status=Release.STATUS_APPROVED, upc=upc)
        for status in self.statuses:
            release.status = status
            release.save()
            self.assertEqual(release.upc, upc)

    @patch('amuse.tasks.zendesk_create_or_update_user')
    def test_created_release_gets_upc_when_status_changes_to_approved(
        self, mocked_zendesk
    ):
        UPCFactory(status=UPC.STATUS_UNUSED)
        release = ReleaseFactory(status=Release.STATUS_SUBMITTED, upc=None)
        release.status = Release.STATUS_APPROVED
        release.save()
        self.assertIsNotNone(release.upc)

    @patch('amuse.tasks.zendesk_create_or_update_user')
    def test_created_by_column(self, mocked_zendesk):
        release_creator = UserFactory(email="release_creator@example.com")
        release = ReleaseFactory(created_by=release_creator)
        self.assertEqual(release.created_by, release_creator)

    @patch('amuse.tasks.zendesk_create_or_update_user')
    def test_manager_pro_releases(self, mocked_zendesk):
        user1 = UserFactory(is_pro=True)
        user2 = UserFactory()
        user3 = UserFactory()

        release1 = ReleaseFactory(created_by=user1, user=user1)
        release2 = ReleaseFactory(created_by=user2, user=user2)
        release3 = ReleaseFactory(created_by=user3, user=user3)

        pro_releases = Release.objects.pro()
        self.assertEqual(len(pro_releases), 1)
        self.assertEqual(pro_releases.first().id, release1.id)

        free_releases = Release.objects.non_pro()
        self.assertEqual(len(free_releases), 2)

    @patch('amuse.tasks.zendesk_create_or_update_user')
    def test_main_primary_artist(self, mocked_zendesk):
        artist1 = Artistv2Factory()
        artist2 = Artistv2Factory()

        release = ReleaseFactory()
        self.assertIsNone(release.main_primary_artist)

        ReleaseArtistRoleFactory(
            release=release,
            artist=artist1,
            role=ReleaseArtistRole.ROLE_PRIMARY_ARTIST,
            main_primary_artist=False,
        )
        self.assertIsNone(release.main_primary_artist)

        ReleaseArtistRoleFactory(
            release=release,
            artist=artist2,
            role=ReleaseArtistRole.ROLE_PRIMARY_ARTIST,
            main_primary_artist=True,
        )
        self.assertEqual(artist2, release.main_primary_artist)

    @patch('amuse.tasks.zendesk_create_or_update_user')
    def test_included_country_codes(self, mocked_zendesk):
        included_country = CountryFactory(code="US")
        excluded_country = CountryFactory(code="FI")

        release = ReleaseFactory()
        release.excluded_countries.add(excluded_country)

        assert list(release.included_country_codes) == ["US"]

    @patch('amuse.tasks.zendesk_create_or_update_user')
    def test_set_status_deleted_on_allowed_status(self, mocked_zendesk):
        release = ReleaseFactory(status=Release.STATUS_PENDING)
        assert release.set_status_deleted() is True

        release.refresh_from_db()
        assert release.status == Release.STATUS_DELETED

    @patch('amuse.tasks.zendesk_create_or_update_user')
    def test_set_status_deleted_on_unallowed_status(self, mocked_zendesk):
        release = ReleaseFactory(status=Release.STATUS_RELEASED)
        assert release.set_status_deleted() is False

        release.refresh_from_db()
        assert release.status == Release.STATUS_RELEASED

    @patch('amuse.tasks.post_slack_release_created.delay')
    def test_release_created_slack_task_called(self, mocked_slack_task):
        release = ReleaseFactory(status=Release.STATUS_SUBMITTED)

        mocked_slack_task.assert_called_once()
