from django.test import TestCase
from users.tests.factories import Artistv2Factory
from releases.tests.factories import (
    ReleaseFactory,
    SongFactory,
    ReleaseArtistRoleFactory,
)
from releases.models import Release, ReleaseArtistRole
from django.db import IntegrityError


class TestReleaseArtistRole(TestCase):
    def test_create_release_artist_role(self):
        release = ReleaseFactory()
        release_user = release.user
        release_user.create_artist_v2(name=release_user.artist_name)
        user_artist_role_set = release_user.userartistrole_set.get(user=release_user)
        release_artist_role = ReleaseArtistRole.objects.create(
            release=release,
            artist=user_artist_role_set.artist,
            role=ReleaseArtistRole.ROLE_PRIMARY_ARTIST,
        )
        self.assertEqual(release, release_artist_role.release)
        self.assertEqual(user_artist_role_set.artist, release_artist_role.artist)
        self.assertEqual(release_user, user_artist_role_set.user)

    def test_geting_release_from_artistv2(self):
        release = ReleaseFactory()
        release_user = release.user
        release_user.create_artist_v2(name=release_user.artist_name)
        user_artist_role_set = release_user.userartistrole_set.get(user=release_user)
        release_artist_role = ReleaseArtistRole.objects.create(
            release=release,
            artist=user_artist_role_set.artist,
            role=ReleaseArtistRole.ROLE_PRIMARY_ARTIST,
        )
        artist_v2 = release_artist_role.artist
        releaseartistrole_set = artist_v2.releaseartistrole_set.get(release=release)
        self.assertEqual(releaseartistrole_set.release, release)

    def test_uniqe_artist_release_constraint(self):
        release = ReleaseFactory()
        release_user = release.user
        release_user.create_artist_v2(name=release_user.artist_name)
        user_artist_role_set = release_user.userartistrole_set.get(user=release_user)
        ReleaseArtistRole.objects.create(
            release=release,
            artist=user_artist_role_set.artist,
            role=ReleaseArtistRole.ROLE_PRIMARY_ARTIST,
        )
        with self.assertRaises(IntegrityError) as context:
            ReleaseArtistRole.objects.create(
                release=release,
                artist=user_artist_role_set.artist,
                role=ReleaseArtistRole.ROLE_PRIMARY_ARTIST,
            )
        self.assertTrue(IntegrityError, type(context.exception))
        self.assertTrue(
            'duplicate key value violates unique constraint' in str(context.exception)
        )

    def test_role_fetching(self):
        keyword1 = 'primary_artist'
        keyword2 = 'mixer'

        role1 = ReleaseArtistRole.get_role_for_keyword(keyword1)
        role2 = ReleaseArtistRole.get_role_for_keyword(keyword2)

        self.assertEqual(role1, ReleaseArtistRole.ROLE_PRIMARY_ARTIST)
        self.assertEqual(role2, ReleaseArtistRole.ROLE_FEATURED_ARTIST)

    def test_role_keyword_missing(self):
        """
        Default role is Featured Artist
        """
        keyword = 'delivery_driver'
        role = ReleaseArtistRole.get_role_for_keyword(keyword)

        self.assertEqual(role, ReleaseArtistRole.ROLE_FEATURED_ARTIST)

    def test_reject_multiple_main_primary_artist_on_release(self):
        release = ReleaseFactory()
        artist = Artistv2Factory()
        releaseartistrole = ReleaseArtistRoleFactory(
            artist=artist, release=release, main_primary_artist=True
        )
        assert len(ReleaseArtistRole.objects.all()) == 1

        artist_2 = Artistv2Factory()
        with self.assertRaises(IntegrityError) as context:
            releaseartistrole_2 = ReleaseArtistRoleFactory(
                artist=artist_2, release=release, main_primary_artist=True
            )

        assert len(ReleaseArtistRole.objects.all()) == 1
        assert (
            'Main Primary Artist already exists. This Error also occurs if you modify already set Main Primary Artist.'
            in str(context.exception)
        )

        artist_3 = Artistv2Factory()
        releaseartistrole_3 = ReleaseArtistRoleFactory(
            artist=artist_3, release=release, main_primary_artist=False
        )
        assert len(ReleaseArtistRole.objects.all()) == 2

    def test_reject_removing_main_primary_artist_on_release(self):
        release = ReleaseFactory()
        artist = Artistv2Factory()
        releaseartistrole = ReleaseArtistRoleFactory(
            artist=artist, release=release, main_primary_artist=True
        )
        assert len(ReleaseArtistRole.objects.all()) == 1

        with self.assertRaises(IntegrityError) as context:
            releaseartistrole.main_primary_artist = False
            releaseartistrole.save()

        assert 'Chosen artist is main primary artist. This can not be unset.' in str(
            context.exception
        )

    def test_reject_editing_main_primary_artist(self):
        release = ReleaseFactory()
        artist = Artistv2Factory()
        releaseartistrole = ReleaseArtistRoleFactory(
            artist=artist, release=release, artist_sequence=1, main_primary_artist=True
        )

        with self.assertRaises(IntegrityError) as context:
            releaseartistrole.artist_sequence = 2
            releaseartistrole.save()

        assert len(ReleaseArtistRole.objects.all()) == 1
        assert (
            'Main Primary Artist already exists. This Error also occurs if you modify already set Main Primary Artist.'
            in str(context.exception)
        )

    def test_allow_editing_non_main_primary_artists(self):
        release = ReleaseFactory()
        artist = Artistv2Factory()

        releaseartistrole = ReleaseArtistRoleFactory(
            artist=artist, release=release, artist_sequence=1, main_primary_artist=False
        )

        releaseartistrole.artist_sequence = 2
        releaseartistrole.save()
        releaseartistrole.refresh_from_db()

        assert releaseartistrole.artist_sequence == 2

    def test_additional_releaseartistroles_is_never_main_primary_artist(self):
        release = ReleaseFactory()
        artist = Artistv2Factory()

        releaseartistrole = ReleaseArtistRoleFactory(
            artist=artist, release=release, artist_sequence=1, main_primary_artist=True
        )

        assert len(ReleaseArtistRole.objects.all()) == 1

        artist_2 = Artistv2Factory()

        releaseartistrole_2 = ReleaseArtistRoleFactory(
            artist=artist_2,
            release=release,
            artist_sequence=1,
            main_primary_artist=None,
        )

        assert len(ReleaseArtistRole.objects.all()) == 2
        releaseartistrole_2.refresh_from_db()
        assert releaseartistrole_2.main_primary_artist is False
