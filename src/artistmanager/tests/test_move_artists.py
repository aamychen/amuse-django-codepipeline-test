from decimal import Decimal
from datetime import datetime, timezone, timedelta
from amuse.tests.test_api.base import AmuseAPITestCase
from users.models import ArtistV2, UserArtistRole
from releases.models import RoyaltySplit, Release
from users.tests.factories import (
    UserFactory,
    Artistv2Factory,
    UserArtistRoleFactory,
)
from releases.tests.factories import (
    ReleaseFactory,
    ReleaseArtistRoleFactory,
    SongFactory,
    SongArtistRoleFactory,
    RoyaltySplitFactory,
)
from artistmanager.move_artists import MoveArtists


class TestMoveArtistsSetUp(AmuseAPITestCase):
    def setUp(self):
        self.old_user = UserFactory()
        self.new_user = UserFactory()
        self.old_user_artist = Artistv2Factory(name='Cat', owner=self.old_user)
        self.uar_old_user = UserArtistRoleFactory(
            user=self.old_user,
            artist=self.old_user_artist,
        )
        self.release = ReleaseFactory(user=self.old_user)
        self.rar = ReleaseArtistRoleFactory(
            release=self.release,
            artist=self.old_user_artist,
        )
        self.song = SongFactory(release=self.release)
        self.sar = SongArtistRoleFactory(
            song=self.song,
            artist=self.old_user_artist,
            artist_sequence=1,
        )
        self.royalty = RoyaltySplitFactory(
            song=self.song,
            user=self.old_user,
            status=RoyaltySplit.STATUS_ACTIVE,
            is_owner=True,
        )

        self.mover = MoveArtists(
            artists_list=[self.old_user_artist.id], new_user_id=self.new_user.id
        )


class TestMoveArtistBase(TestMoveArtistsSetUp):
    def setUp(self):
        super(TestMoveArtistBase, self).setUp()

    def test_move_artist_init(self):
        self.assertEqual(self.mover.new_user, self.new_user)
        self.assertEqual(len(self.mover.artists_list), 1)

    def test_get_artist_old_user_map(self):
        artist_old_user_map = self.mover.get_artist_old_user_map()
        self.assertEqual(
            artist_old_user_map.get(self.old_user_artist.id), self.old_user
        )

    def test_song_have_peding_splits(self):
        self.assertFalse(self.mover.song_have_pending_splits(self.song))

    def test_get_splits_for_update(self):
        splits = self.mover.get_splits_for_update(artist_id=self.old_user_artist.id)
        split = splits[:1].get()
        self.assertEqual(splits.count(), 1)
        self.assertEqual(split.user, self.old_user)
        self.assertEqual(split.status, RoyaltySplit.STATUS_ACTIVE)
        self.assertEqual(split.song, self.song)

    def test_update_artist_v2_to_new_user(self):
        self.mover.update_artist_v2_to_new_user()
        artist = ArtistV2.objects.get(id=self.old_user_artist.id)
        self.assertEqual(artist.owner, self.new_user)

    def test_change_old_user_to_admin(self):
        self.mover.change_old_user_to_admin(
            user=self.old_user, artist_id=self.old_user_artist.id
        )
        uar_new = UserArtistRole.objects.get(
            user=self.old_user, artist=self.old_user_artist
        )
        self.assertEqual(uar_new.type, UserArtistRole.ADMIN)

    def test_update_userartistrole_to_new_user(self):
        self.mover.add_new_user_as_owner(artist_id=self.old_user_artist.id)
        uar = UserArtistRole.objects.get(
            artist=self.old_user_artist, user=self.new_user
        )
        self.assertEqual(uar.type, UserArtistRole.OWNER)

    def test_update_split(self):
        self.mover.update_split(
            old_split=self.royalty, new_user=self.new_user, old_user=self.old_user
        )
        old_split = RoyaltySplit.objects.get(user=self.old_user)
        self.assertEqual(old_split.status, RoyaltySplit.STATUS_ARCHIVED)
        new_split = RoyaltySplit.objects.get(user=self.new_user)
        self.assertEqual(new_split.status, RoyaltySplit.STATUS_ACTIVE)
        self.assertEqual(old_split.rate, new_split.rate)
        self.assertEqual(new_split.revision, old_split.revision + 1)
        self.assertEqual(new_split.is_owner, True)

    def test_update_releases_to_new_user(self):
        self.mover.update_releases_to_new_user(self.old_user_artist)
        release = Release.objects.get(id=self.release.id)
        self.assertEqual(release.user, self.new_user)

    def test_execute_move_artists(self):
        self.mover.execute_move_artists()
        artist = ArtistV2.objects.get(id=self.old_user_artist.id)
        self.assertEqual(artist.owner, self.new_user)
        uar = UserArtistRole.objects.get(
            artist=self.old_user_artist, user=self.new_user
        )
        self.assertEqual(uar.type, UserArtistRole.OWNER)
        self.assertEqual(uar.user, self.new_user)
        old_split = RoyaltySplit.objects.get(user=self.old_user)
        self.assertEqual(old_split.status, RoyaltySplit.STATUS_ARCHIVED)
        self.assertIsNotNone(old_split.end_date)
        new_split = RoyaltySplit.objects.get(user=self.new_user)
        self.assertEqual(new_split.status, RoyaltySplit.STATUS_ACTIVE)
        self.assertEqual(old_split.rate, new_split.rate)
        self.assertEqual(new_split.revision, old_split.revision + 1)
        self.assertEqual(new_split.is_owner, True)
        self.assertIsNotNone(new_split.start_date)
        release = Release.objects.get(id=self.release.id)
        self.assertEqual(release.user, self.new_user)


class TestMoveArtistsExtended(TestMoveArtistsSetUp):
    def setUp(self):
        super(TestMoveArtistsExtended, self).setUp()
        self.unrelated_user = UserFactory()
        self.unrelated_user2 = UserFactory()
        self.old_user_artist2 = Artistv2Factory(name='Dog', owner=self.old_user)
        self.old_user_artist3 = Artistv2Factory(name='Dog2', owner=self.old_user)
        self.uar_old_user = UserArtistRoleFactory(
            user=self.old_user,
            artist=self.old_user_artist2,
        )
        self.existing_role = UserArtistRoleFactory(
            user=self.new_user, artist=self.old_user_artist, type=UserArtistRole.MEMBER
        )
        self.unrelated_release = ReleaseFactory(user=self.old_user)
        self.unrelated_rar = ReleaseArtistRoleFactory(
            release=self.unrelated_release, artist=self.old_user_artist3
        )

        self.song2 = SongFactory(release=self.release)
        self.sar2 = SongArtistRoleFactory(
            song=self.song2,
            artist=self.old_user_artist2,
            artist_sequence=1,
        )

        self.royalty2 = RoyaltySplitFactory(
            song=self.song2,
            user=self.old_user,
            status=RoyaltySplit.STATUS_ACTIVE,
            rate=0.8,
            is_owner=True,
        )
        self.royalty3 = RoyaltySplitFactory(
            song=self.song2,
            user=self.unrelated_user,
            status=RoyaltySplit.STATUS_ACTIVE,
            rate=0.1,
        )

        self.royalty4 = RoyaltySplitFactory(
            song=self.song2,
            user=self.unrelated_user2,
            status=RoyaltySplit.STATUS_PENDING,
            rate=0.1,
        )

        # Song without PENDING splits and already changed splits revision
        self.song3 = SongFactory(release=self.release)
        self.sar3 = SongArtistRoleFactory(
            song=self.song3,
            artist=self.old_user_artist2,
            artist_sequence=1,
        )

        self.royalty5 = RoyaltySplitFactory(
            song=self.song3,
            user=self.old_user,
            status=RoyaltySplit.STATUS_ACTIVE,
            rate=0.8,
            is_owner=True,
            revision=2,
        )
        self.royalty6 = RoyaltySplitFactory(
            song=self.song3,
            user=self.unrelated_user,
            status=RoyaltySplit.STATUS_ACTIVE,
            rate=0.1,
            revision=2,
        )

        self.royalty7 = RoyaltySplitFactory(
            song=self.song3,
            user=self.unrelated_user2,
            status=RoyaltySplit.STATUS_ACTIVE,
            rate=0.1,
            revision=2,
        )
        self.mover = MoveArtists(
            artists_list=[self.old_user_artist.id, self.old_user_artist2.id],
            new_user_id=self.new_user.id,
        )

        # Song WITH ARCHIVED and ACTIVE split
        self.song4 = SongFactory(release=self.release)
        self.sar4 = SongArtistRoleFactory(
            song=self.song4,
            artist=self.old_user_artist2,
            artist_sequence=1,
        )

        self.royalty8 = RoyaltySplitFactory(
            song=self.song4,
            user=self.old_user,
            rate=1.0,
            is_owner=True,
            status=RoyaltySplit.STATUS_ARCHIVED,
        )

        self.royalty9 = RoyaltySplitFactory(
            song=self.song4,
            user=self.old_user,
            rate=1.0,
            is_owner=True,
            status=RoyaltySplit.STATUS_ACTIVE,
            revision=2,
        )

    def test_extended_case(self):
        self.mover.execute_move_artists()
        artist = ArtistV2.objects.get(id=self.old_user_artist2.id)
        self.assertEqual(artist.owner, self.new_user)
        uar = UserArtistRole.objects.get(
            artist=self.old_user_artist2, user=self.new_user
        )
        self.assertEqual(uar.type, UserArtistRole.OWNER)
        uar_old = UserArtistRole.objects.get(
            artist=self.old_user_artist2, user=self.old_user
        )
        self.assertEqual(uar_old.type, UserArtistRole.ADMIN)
        release = Release.objects.get(id=self.release.id)
        self.assertEqual(release.user, self.new_user)

        # Assert splits for song2 are unchanged
        split1 = RoyaltySplit.objects.get(song=self.song2, user=self.old_user)
        self.assertEqual(split1.revision, 1)
        self.assertEqual(split1.rate, Decimal('0.8'))
        self.assertEqual(split1.status, RoyaltySplit.STATUS_ACTIVE)

        split2 = RoyaltySplit.objects.get(song=self.song2, user=self.unrelated_user)
        self.assertEqual(split2.revision, 1)
        self.assertEqual(split2.rate, Decimal('0.1'))
        self.assertEqual(split2.status, RoyaltySplit.STATUS_ACTIVE)

        split3 = RoyaltySplit.objects.get(song=self.song2, user=self.unrelated_user2)
        self.assertEqual(split2.revision, 1)
        self.assertEqual(split3.rate, Decimal('0.1'))
        self.assertEqual(split3.status, RoyaltySplit.STATUS_PENDING)

        # Assert splits for song3 correctly archived
        today = datetime.now(timezone.utc).date()
        end_date = today - timedelta(days=1)

        split4 = RoyaltySplit.objects.get(song=self.song3, user=self.old_user)
        self.assertEqual(split4.revision, 2)
        self.assertEqual(split4.rate, Decimal('0.8'))
        self.assertEqual(split4.status, RoyaltySplit.STATUS_ARCHIVED)
        self.assertEqual(split4.end_date, end_date)

        split5 = RoyaltySplit.objects.get(id=self.royalty6.id)
        self.assertEqual(split5.user, self.unrelated_user)
        self.assertEqual(split5.revision, 2)
        self.assertEqual(split5.rate, Decimal('0.1'))
        self.assertEqual(split5.status, RoyaltySplit.STATUS_ARCHIVED)
        self.assertEqual(split5.end_date, end_date)

        split6 = RoyaltySplit.objects.get(id=self.royalty7.id)
        self.assertEqual(split6.user, self.unrelated_user2)
        self.assertEqual(split6.revision, 2)
        self.assertEqual(split6.rate, Decimal('0.1'))
        self.assertEqual(split6.status, RoyaltySplit.STATUS_ARCHIVED)
        self.assertEqual(split6.end_date, end_date)

        # Assert new splits created correctly
        split7 = RoyaltySplit.objects.get(song=self.song3, user=self.new_user)
        self.assertEqual(split7.revision, 3)
        self.assertEqual(split7.rate, Decimal('0.8'))
        self.assertEqual(split7.status, RoyaltySplit.STATUS_ACTIVE)
        self.assertTrue(split7.is_owner)
        self.assertEqual(split7.start_date, today)

        split8 = RoyaltySplit.objects.get(
            song=self.song3, user=self.unrelated_user, status=RoyaltySplit.STATUS_ACTIVE
        )
        self.assertEqual(split8.revision, 3)
        self.assertEqual(split8.rate, Decimal('0.1'))
        self.assertEqual(split8.start_date, today)

        split9 = RoyaltySplit.objects.get(
            song=self.song3,
            user=self.unrelated_user2,
            status=RoyaltySplit.STATUS_ACTIVE,
        )
        self.assertEqual(split9.revision, 3)
        self.assertEqual(split9.rate, Decimal('0.1'))
        self.assertEqual(split9.start_date, today)

        # Assert case with exiting ARCHIVED split with moved revision

        split10 = RoyaltySplit.objects.get(id=self.royalty8.id)
        self.assertEqual(split10.revision, 1)
        self.assertEqual(split10.status, RoyaltySplit.STATUS_ARCHIVED)

        split11 = RoyaltySplit.objects.get(user=self.new_user, song=self.song4)
        self.assertEqual(split11.rate, Decimal('1.0'))
        self.assertEqual(split11.revision, 3)
        self.assertEqual(split11.status, RoyaltySplit.STATUS_ACTIVE)
        self.assertTrue(split11.is_owner)

        # Assert only releases where moved artist is PRIMATY_ARTIST are changed
        unrelated_release = Release.objects.get(id=self.unrelated_release.id)
        self.assertEquals(unrelated_release.user, self.old_user)
