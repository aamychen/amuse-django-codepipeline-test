from decimal import Decimal

import responses
from django.test import TestCase, override_settings
from django.utils import timezone
from simple_history.manager import HistoryManager

from amuse.api.v4.serializers.helpers import get_serialized_active_royalty_splits
from amuse.tests.helpers import (
    ZENDESK_MOCK_API_URL_TOKEN,
    add_zendesk_mock_post_response,
)
from codes.models import ISRC, UPC
from codes.tests.factories import ISRCFactory, UPCFactory
from releases.models import Release, RoyaltySplit, Song, SongArtistRole
from releases.models.exceptions import (
    ArtistsIDsDoNotExistError,
    SongsIDsDoNotExistError,
)
from releases.tests.factories import (
    ReleaseFactory,
    RoyaltySplitFactory,
    SongArtistRoleFactory,
    SongFactory,
)
from users.tests.factories import Artistv2Factory, UserFactory


@override_settings(**ZENDESK_MOCK_API_URL_TOKEN)
class SongTestCase(TestCase):
    def setUp(self):
        add_zendesk_mock_post_response()

    @responses.activate
    def test_song_history(self):
        """Song model history is enabled."""
        song = Song()
        self.assertTrue(isinstance(song.history, HistoryManager))
        self.assertEqual(song.history.count(), 0)

        song = SongFactory()
        # 2 because https://github.com/FactoryBoy/factory_boy/issues/316
        self.assertEqual(song.history.count(), 2)

    @responses.activate
    def test_song_created_without_isrc_assinged(self):
        release = ReleaseFactory(status=Release.STATUS_SUBMITTED, upc=None)
        song = SongFactory(release=release, isrc=None)
        self.assertIsNone(song.isrc)

    @responses.activate
    def test_isrc_code_property_returns_none_when_isrc_is_not_assigned(self):
        release = ReleaseFactory(status=Release.STATUS_SUBMITTED, upc=None)
        song = SongFactory(release=release, isrc=None)
        self.assertIsNone(song.isrc_code)

    @responses.activate
    def test_isrc_code_property_returns_code_when_isrc_is_assigned(self):
        release = ReleaseFactory(status=Release.STATUS_SUBMITTED, upc=None)
        song = SongFactory(release=release, isrc=None)
        isrc = ISRCFactory()
        song.isrc = isrc
        self.assertEqual(song.isrc_code, isrc.code)

    @responses.activate
    def test_song_doesnt_have_isrc_created_while_release_not_approved(self):
        release = ReleaseFactory(status=Release.STATUS_SUBMITTED, upc=None)
        song = SongFactory(release=release, isrc=None)
        self.assertIsNone(song.isrc)

    @responses.activate
    def test_song_gets_isrc_created_when_release_is_approved(self):
        release = ReleaseFactory(status=Release.STATUS_SUBMITTED, upc=None)
        song = SongFactory(release=release, isrc=None)
        isrc = ISRCFactory(status=ISRC.STATUS_UNUSED)
        upc = UPCFactory(status=UPC.STATUS_UNUSED)
        self.assertIsNone(song.isrc)
        release.status = Release.STATUS_APPROVED
        release.save()
        song.save()
        self.assertIsNotNone(song.isrc)
        self.assertEqual(song.isrc, isrc)

    @responses.activate
    def test_artists_roles(self):
        artist = Artistv2Factory()
        song = SongFactory()
        song_artist_role = SongArtistRoleFactory(artist=artist, song=song)
        self.assertEqual(
            song.artists_roles,
            [
                {
                    'artist_id': song_artist_role.artist_id,
                    'roles': [song_artist_role.get_role_display()],
                }
            ],
        )

    @responses.activate
    def test_royalty_splits(self):
        user_1 = UserFactory()
        user_2 = UserFactory()

        song = SongFactory()
        rate = Decimal("1.0")

        # First royalty_split has user_1 and status pending which the default value.
        royalty_split = RoyaltySplitFactory(
            user=user_1,
            song=song,
            rate=rate,
            revision=1,
            status=RoyaltySplit.STATUS_ACTIVE,
        )

        # Second royalty_split which has same song but no user with status pending
        RoyaltySplitFactory(
            user=None,
            song=song,
            rate=rate,
            revision=2,
            status=RoyaltySplit.STATUS_PENDING,
        )

        # We expect to have only one royalty split because the one of the two
        # royalty splits has status pending.
        self.assertEqual(len(get_serialized_active_royalty_splits(song)), 1)
        expected_royalty_splits = [
            {
                'name': user_1.name,
                'photo': royalty_split.get_user_profile_photo_url(),
                'rate': rate,
            }
        ]
        self.assertEqual(
            get_serialized_active_royalty_splits(song), expected_royalty_splits
        )

    @responses.activate
    def test_get_primary_artists(self):
        artist = Artistv2Factory()
        writer = Artistv2Factory()
        song = SongFactory()
        song_artist_role = SongArtistRoleFactory(artist=artist, song=song)
        song_artist_role = SongArtistRoleFactory(
            artist=writer, song=song, role=SongArtistRole.ROLE_WRITER
        )

        primary_artists = song.get_primary_artists()

        self.assertEqual(len(primary_artists), 1)
        self.assertEqual(primary_artists[0], artist)


@override_settings(**ZENDESK_MOCK_API_URL_TOKEN)
class SongArtistRoleTestCase(TestCase):
    def setUp(self):
        add_zendesk_mock_post_response()

    @responses.activate
    def test_get_songs_ids_by_artist_id_raises_an_exception(self):
        # Fake artist ID.
        artist_id = 123

        # We expect no song_id to be returned therefore
        # SongsIDsDoNotExistError exception will be raised instead.
        with self.assertRaisesMessage(
            SongsIDsDoNotExistError, 'Artist does not have any songs.'
        ):
            SongArtistRole.get_songs_ids_by_artist_id(artist_id)

    @responses.activate
    def test_get_songs_ids_by_artist_id_returns_songs_ids(self):
        artist = Artistv2Factory()
        song = SongFactory()
        SongArtistRoleFactory(artist=artist, song=song)

        # Adding a second song should not affect the number of songs IDs
        # returned.
        SongFactory()

        songs_ids = SongArtistRole.get_songs_ids_by_artist_id(artist.id)

        # We only expect one song belongs to the artist to be returned
        # while the second song will be ignored.
        self.assertQuerysetEqual(songs_ids, [song.id], int)

    @responses.activate
    def test_get_artists_ids_by_songs_ids_raises_an_exception(self):
        artist_1 = Artistv2Factory()
        artist_2 = Artistv2Factory()

        song_1 = SongFactory()
        song_2 = SongFactory()

        SongArtistRoleFactory(artist=artist_1, song=song_1)
        # artist_2 has his own song and did not contribute with artist_1.
        SongArtistRoleFactory(artist=artist_2, song=song_2)

        # We only expect the the song belongs to artist_1 to be returned.
        songs_ids = SongArtistRole.get_songs_ids_by_artist_id(artist_1.id)

        # We except no artist_id to be returned because artist_2 didn't have a
        # common song with artist_1 there for ArtistsIDsDoNotExistError
        # excption will be raised.
        with self.assertRaisesMessage(
            ArtistsIDsDoNotExistError,
            'Artists does not have any previously contributed artists.',
        ):
            SongArtistRole.get_artists_ids_by_songs_ids(artist_1.id, songs_ids)

    @responses.activate
    def test_get_artists_ids_by_songs_ids_returns_artists_ids(self):
        artist_1 = Artistv2Factory()
        artist_2 = Artistv2Factory()
        artist_3 = Artistv2Factory()

        song_1 = SongFactory()
        song_2 = SongFactory()

        SongArtistRoleFactory(artist=artist_1, song=song_1)
        # artist_2 has contributed with artist_1 on song_1.
        SongArtistRoleFactory(artist=artist_2, song=song_1)
        # artist_3 has his own song and did not contribute with artist_1 or
        # artist_2.
        SongArtistRoleFactory(artist=artist_3, song=song_2)

        # We only expect the song_1 which belongs to artist_1 and artist_2 to
        # be returned while song_2 will be ignored because it belongs to
        # artist_3.
        songs_ids = SongArtistRole.get_songs_ids_by_artist_id(artist_1.id)

        artists_ids = SongArtistRole.get_artists_ids_by_songs_ids(
            artist_1.id, songs_ids
        )

        # We expect only artist_2 to be returned because we need to exclude artist_1
        # while the artist_3 will be ignored since he did not contributed with
        # artist_1.
        self.assertQuerysetEqual(artists_ids, [artist_2.id], int)

    @responses.activate
    def test_get_artists_ids_by_songs_ids_returns_artists_ids_excluding_artist_with_writer_role_in_same_songs(
        self,
    ):
        artist_1 = Artistv2Factory()
        artist_2 = Artistv2Factory()
        artist_3 = Artistv2Factory()

        song_1 = SongFactory()

        SongArtistRoleFactory(artist=artist_1, song=song_1)
        # artist_2 has contributed with artist_1 on song_1.
        SongArtistRoleFactory(artist=artist_2, song=song_1)
        # artist_3 has contributed with artist_1 on song 1 but as a writer
        SongArtistRoleFactory(
            artist=artist_3, song=song_1, role=SongArtistRole.ROLE_WRITER
        )
        SongArtistRoleFactory(
            artist=artist_3, song=song_1, role=SongArtistRole.ROLE_MIXER
        )

        songs_ids = [song_1.id]
        artists_ids = SongArtistRole.get_artists_ids_by_songs_ids(
            artist_1.id, songs_ids
        )

        # We expect artist_2 and artist_3 to be returned because we need to
        # exclude artist_1 but not artist_3 even though he has writer role,
        # because he has another role too.
        self.assertQuerysetEqual(artists_ids, [artist_2.id, artist_3.id], int)

    @responses.activate
    def test_get_artists_ids_by_songs_ids_returns_artists_ids_excluding_artist_with_writer_role_in_different_songs(
        self,
    ):
        artist_1 = Artistv2Factory()
        artist_2 = Artistv2Factory()
        artist_3 = Artistv2Factory()

        song_1 = SongFactory()
        song_2 = SongFactory()

        SongArtistRoleFactory(artist=artist_1, song=song_1)
        # artist_2 has contributed with artist_1 on song_1.
        SongArtistRoleFactory(artist=artist_2, song=song_1)
        # artist_3 has contributed with artist_1 on song 1 but as a writer.
        SongArtistRoleFactory(
            artist=artist_3, song=song_1, role=SongArtistRole.ROLE_WRITER
        )

        SongArtistRoleFactory(artist=artist_1, song=song_2)
        # artist_3 has contributed with artist_1 on song 2 but not as a writer.
        SongArtistRoleFactory(
            artist=artist_3, song=song_2, role=SongArtistRole.ROLE_MIXER
        )

        songs_ids = [song_1.id, song_2.id]
        artists_ids = SongArtistRole.get_artists_ids_by_songs_ids(
            artist_1.id, songs_ids
        )

        # We expect artist_2 and artist_3 to be returned because we need to
        # exclude artist_1 but not artist_3 even though he has writer role,
        # because he has another role too in different song.
        self.assertQuerysetEqual(artists_ids, [artist_2.id, artist_3.id], int)

    @responses.activate
    def test_get_next_royalty_split_revision(self):
        add_zendesk_mock_post_response()

        user_1 = UserFactory()
        song = SongFactory()

        royalty_split_1 = RoyaltySplitFactory(
            user=user_1,
            song=song,
            start_date=timezone.now().today(),
            rate=0.5,
            status=RoyaltySplit.STATUS_ACTIVE,
        )

        user_2 = UserFactory()
        royalty_split_2 = RoyaltySplitFactory(
            user=user_2,
            song=song,
            start_date=timezone.now().today(),
            rate=0.5,
            status=RoyaltySplit.STATUS_PENDING,
        )

        # By default revision will be 1.
        self.assertEqual(royalty_split_1.revision, 1)
        self.assertEqual(royalty_split_2.revision, 1)

        # We expect the get_next_royalty_split_revision to return 2 as next revision.
        self.assertEqual(song.get_next_royalty_split_revision(), 2)

    @responses.activate
    def test_get_next_royalty_split_revision_when_song_doesnt_have_royalty_splits(self):
        song = SongFactory()

        # We expect the get_next_royalty_split_revision to return 1 as next revision
        # since there no royalty splits created yet.
        self.assertEqual(song.get_next_royalty_split_revision(), 1)

    @responses.activate
    def test_set_value_preview_start_time_field(self):
        song = SongFactory(preview_start_time=30)
        self.assertEqual(song.preview_start_time, 30)
