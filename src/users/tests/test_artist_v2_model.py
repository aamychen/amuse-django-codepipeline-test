from django.db import IntegrityError
from django.test import TestCase, override_settings
import responses

from amuse.tests.helpers import (
    add_zendesk_mock_post_response,
    ZENDESK_MOCK_API_URL_TOKEN,
)
from users.models.artist_v2 import ArtistV2, UserArtistRole
from users.models.exceptions import ArtistsDoNotExistError
from users.tests.factories import UserFactory, Artistv2Factory


@override_settings(**ZENDESK_MOCK_API_URL_TOKEN)
class ArtistV2TestCase(TestCase):
    def setUp(self):
        add_zendesk_mock_post_response()

    def test_user_artist_role_get_name(self):
        self.assertEqual(UserArtistRole.get_name(1), 'admin')
        self.assertEqual(UserArtistRole.get_name(2), 'member')
        self.assertEqual(UserArtistRole.get_name(3), 'owner')
        self.assertEqual(UserArtistRole.get_name(4), 'spectator')
        self.assertEqual(UserArtistRole.get_name(5), 'superadmin')

    @responses.activate
    def test_artist_from_user(self):
        cat = UserFactory(artist_name='UberCat')
        cat.create_artist_v2(name=cat.artist_name)
        self.assertEqual(ArtistV2.objects.get(name='UberCat').name, 'UberCat')
        self.assertEqual(
            UserArtistRole.objects.get(
                artist=ArtistV2.objects.get(name='UberCat')
            ).user,
            cat,
        )
        self.assertEqual(
            UserArtistRole.objects.get(
                artist=ArtistV2.objects.get(name='UberCat'), user=cat
            ).type,
            UserArtistRole.OWNER,
        )

    @responses.activate
    def test_artist_and_role_create(self):
        lion = UserFactory()
        lionsArtist = lion.create_artist_v2(name=lion.artist_name)
        self.assertEqual(
            UserArtistRole.objects.get(artist=lionsArtist).artist, lionsArtist
        )
        self.assertEqual(UserArtistRole.objects.get(artist=lionsArtist).user, lion)
        self.assertEqual(UserArtistRole.objects.get(artist=lionsArtist).type, 3)

    @responses.activate
    def test_uniqe_constraint(self):
        lion = UserFactory()
        cat = UserFactory()
        lionsArtist = ArtistV2.objects.create(name='lionsArtist')
        UserArtistRole.objects.create(
            user=cat, artist=lionsArtist, type=UserArtistRole.MEMBER
        )
        with self.assertRaises(IntegrityError) as context:
            UserArtistRole.objects.create(
                user=cat, artist=lionsArtist, type=UserArtistRole.MEMBER
            )
        self.assertTrue(IntegrityError, type(context.exception))
        self.assertTrue(
            'duplicate key value violates unique constraint' in str(context.exception)
        )

    @responses.activate
    def test_update_artistv2_from_user_deprecated(self):
        cat = UserFactory(artist_name='UberCat')
        cat_artist = ArtistV2.objects.create(name="UberCat")
        UserArtistRole.objects.create(
            user=cat, artist=cat_artist, type=UserArtistRole.OWNER
        )
        cat.artist_name = "Changed"
        cat.save()
        cat_artist.refresh_from_db()
        self.assertEqual(cat_artist.name, 'UberCat')

    @responses.activate
    def test_has_owner_property_with_owner_returns_true(self):
        user = UserFactory()
        artist = Artistv2Factory(owner=user)
        self.assertTrue(artist.has_owner)

    @responses.activate
    def test_has_owner_property_with_owner_returns_true(self):
        user = UserFactory()
        artist = Artistv2Factory(owner=user)
        self.assertTrue(artist.has_owner)

    @responses.activate
    def test_get_artists_by_ids_raises_an_exception(self):
        # Fake artist ID.
        artists_ids = [123]

        # We expect no artist to be returned therefore ArtistsDoNotExistError
        # exception will be raised instead.
        with self.assertRaisesMessage(
            ArtistsDoNotExistError, 'Artists were not found.'
        ):
            ArtistV2.get_artists_by_ids(artists_ids)

    @responses.activate
    def test_get_artists_by_ids_returns_artist_objects(self):
        artist_1 = Artistv2Factory()
        artist_2 = Artistv2Factory()
        artist_3 = Artistv2Factory()
        # We picked artist_1 and artist_2 to be fetched but not artist_3
        created_artists_ids = ArtistV2.objects.values_list('id', flat=True).filter(
            id__in=[artist_1.id, artist_2.id]
        )

        artists = ArtistV2.get_artists_by_ids(created_artists_ids)

        # We expect the count of the artist objects returned to be equal to
        # artists_ids passed to get_artists_by_ids.
        self.assertEqual(artists.count(), created_artists_ids.count())
        # We expect artist_1 to be among the returned artists
        self.assertIn(artist_1, artists)
        # We expect artist_2 to be among the returned artists
        self.assertIn(artist_2, artists)
        # We expect artist_3 NOT to be among the returned artists
        self.assertNotIn(artist_3, artists)
