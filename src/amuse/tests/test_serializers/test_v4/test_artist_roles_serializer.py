from django.test import TestCase, override_settings
import responses

from amuse.tests.helpers import (
    add_zendesk_mock_post_response,
    ZENDESK_MOCK_API_URL_TOKEN,
)

from amuse.api.v4.serializers.artist_roles import (
    ArtistRolesSerializer,
    CONFLICTING_ROLES_MESSAGE,
    INVALID_ROLE_MESSAGE,
)
from users.tests.factories import Artistv2Factory


@override_settings(**ZENDESK_MOCK_API_URL_TOKEN)
class TestArtistRolesSerializer(TestCase):
    @responses.activate
    def setUp(self):
        add_zendesk_mock_post_response()
        self.artist = Artistv2Factory()
        self.data = {'roles': ['writer'], 'artist_id': self.artist.id}

        self.expected_error_message = 'This field is required.'

    def test_artist_roles_serializer_data(self):
        serializer = ArtistRolesSerializer(data=self.data)
        self.assertTrue(serializer.is_valid())
        self.assertEqual(serializer.validated_data['artist_id'], self.data['artist_id'])
        self.assertEqual(serializer.validated_data['roles'], self.data['roles'])

    def test_artist_roles_raise_validation_error_when_artist_id_is_missing(self):
        self.data = {'roles': ['writer']}
        serializer = ArtistRolesSerializer(data=self.data)

        self.assertFalse(serializer.is_valid())
        self.assertIn('artist_id', serializer.errors)
        returned_error_message = str(serializer.errors['artist_id'][0])
        self.assertEqual(returned_error_message, self.expected_error_message)

    def test_artist_roles_raise_validation_error_when_roles_are_missing(self):
        self.data = {'artist_id': self.artist.id}
        serializer = ArtistRolesSerializer(data=self.data)

        self.assertFalse(serializer.is_valid())
        self.assertIn('roles', serializer.errors)
        returned_error_message = str(serializer.errors['roles'][0])
        self.assertEqual(returned_error_message, self.expected_error_message)

    def test_artist_roles_raise_validation_error_when_role_is_invalid(self):
        self.data = {'artist_id': self.artist.id, 'roles': ['invalid_role']}
        serializer = ArtistRolesSerializer(data=self.data)

        self.assertFalse(serializer.is_valid())
        self.assertIn('roles', serializer.errors)
        returned_error_message = str(serializer.errors['roles'][0])
        self.assertEqual(returned_error_message, INVALID_ROLE_MESSAGE)

    def test_artist_roles_raise_validation_error_when_roles_are_primary_and_featured(
        self,
    ):
        self.data = {
            'artist_id': self.artist.id,
            'roles': ['primary_artist', 'featured_artist'],
        }
        serializer = ArtistRolesSerializer(data=self.data)

        self.assertFalse(serializer.is_valid())
        self.assertIn('roles', serializer.errors)
        returned_error_message = str(serializer.errors['roles'][0])
        self.assertEqual(returned_error_message, CONFLICTING_ROLES_MESSAGE)
