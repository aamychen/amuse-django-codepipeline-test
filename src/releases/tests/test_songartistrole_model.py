from django.test import TestCase
from releases.tests.factories import SongFactory
from releases.models import SongArtistRole
from users.tests.factories import UserFactory
from django.db import IntegrityError


class TestReleaseArtistRole(TestCase):
    def test_create_song_artist_role(self):
        song = SongFactory()
        song_release = song.release
        song_user = song_release.user
        song_user.create_artist_v2(name=song_user.artist_name)
        user_artist_role_set = song_user.userartistrole_set.get(user=song_user)
        song_artist_role = SongArtistRole.objects.create(
            artist=user_artist_role_set.artist,
            song=song,
            role=SongArtistRole.ROLE_PRIMARY_ARTIST,
        )
        self.assertEqual(song_artist_role.artist, user_artist_role_set.artist)

    def test_get_songs_from_artistv2(self):
        song_A = SongFactory()
        song_A_release = song_A.release
        song_A_user = song_A_release.user
        song_A_user.create_artist_v2(name=song_A_user.artist_name)
        song_A_artist = song_A_user.userartistrole_set.get(user=song_A_user).artist
        song_B = SongFactory(release=song_A_release)
        SongArtistRole.objects.create(
            artist=song_A_artist, song=song_A, role=SongArtistRole.ROLE_PRIMARY_ARTIST
        )
        SongArtistRole.objects.create(
            artist=song_A_artist, song=song_B, role=SongArtistRole.ROLE_PRIMARY_ARTIST
        )
        artist_v2_songs = song_A_artist.songartistrole_set.all()
        self.assertEqual(len(list(artist_v2_songs)), 2)

    def test_assing_song_role(self):
        userA = UserFactory()
        userB = UserFactory()
        userC = UserFactory()
        userA.create_artist_v2(userA.artist_name)
        userB.create_artist_v2(userB.artist_name)
        userC.create_artist_v2(userC.artist_name)
        userA_artist = userA.userartistrole_set.get(user=userA).artist
        userB_artist = userB.userartistrole_set.get(user=userB).artist
        userC_artist = userC.userartistrole_set.get(user=userC).artist
        song = SongFactory()
        SongArtistRole.objects.create(
            artist=userA_artist, song=song, role=SongArtistRole.ROLE_PRIMARY_ARTIST
        )
        SongArtistRole.objects.create(
            song=song, artist=userC_artist, role=SongArtistRole.ROLE_PRODUCER
        )
        SongArtistRole.objects.create(
            song=song, artist=userB_artist, role=SongArtistRole.ROLE_WRITER
        )
        song_all_artist = SongArtistRole.objects.all()
        self.assertTrue(len(list(song_all_artist)) == 3)
        self.assertEqual(SongArtistRole.objects.get(artist=userA_artist).role, 1)
        self.assertEqual(SongArtistRole.objects.get(artist=userB_artist).role, 3)
        self.assertEqual(SongArtistRole.objects.get(artist=userC_artist).role, 4)

    def test_uniqe_song_artist_role_constraint(self):
        song = SongFactory()
        song_release = song.release
        song_user = song_release.user
        song_user.create_artist_v2(name=song_user.artist_name)
        user_artist_role_set = song_user.userartistrole_set.get(user=song_user)
        SongArtistRole.objects.create(
            artist=user_artist_role_set.artist,
            song=song,
            role=SongArtistRole.ROLE_PRIMARY_ARTIST,
        )
        with self.assertRaises(IntegrityError) as context:
            SongArtistRole.objects.create(
                artist=user_artist_role_set.artist,
                song=song,
                role=SongArtistRole.ROLE_PRIMARY_ARTIST,
            )
        self.assertTrue(IntegrityError, type(context.exception))
        self.assertTrue(
            'duplicate key value violates unique constraint' in str(context.exception)
        )

    def test_role_fetching(self):
        keyword1 = 'primary_artist'
        keyword2 = 'mixer'

        role1 = SongArtistRole.get_role_for_keyword(keyword1)
        role2 = SongArtistRole.get_role_for_keyword(keyword2)

        self.assertEqual(role1, SongArtistRole.ROLE_PRIMARY_ARTIST)
        self.assertEqual(role2, SongArtistRole.ROLE_MIXER)

    def test_role_keyword_empty(self):
        """
        No default value anymore, should throw an exception
        """
        with self.assertRaises(ValueError) as context:
            SongArtistRole.get_role_for_keyword("")

        self.assertEqual(
            str(context.exception),
            'No song artist role can be defined due to empty keyword',
        )

    def test_role_keyword_missing(self):
        """
        No default value anymore, should throw an exception
        """
        keyword = 'delivery_driver'
        with self.assertRaises(ValueError) as context:
            SongArtistRole.get_role_for_keyword(keyword)

        self.assertEqual(
            str(context.exception),
            'Song Artist Role for keyword delivery_driver not found',
        )
