from unittest.mock import Mock, patch

from django.test import TestCase, override_settings
import responses

from amuse.api.v4.serializers.artist import (
    ArtistSerializer,
    ArtistSearchSerializer,
    ContibutorArtistSerializer,
)
from amuse.tests.helpers import (
    add_zendesk_mock_post_response,
    ZENDESK_MOCK_API_URL_TOKEN,
)
from users.tests.factories import UserFactory, Artistv2Factory


@override_settings(**ZENDESK_MOCK_API_URL_TOKEN)
class TestArtistSerializer(TestCase):
    @responses.activate
    def setUp(self):
        add_zendesk_mock_post_response()
        user = UserFactory()
        mocked_request = Mock(user=user)

        self.data = {
            'name': 'Test Artist v2',
            'spotify_page': 'https://spotify.com/artists/123',
            'twitter_name': 'artistv2',
            'facebook_page': 'https://www.facebook.com/pages/artistv2',
            'instagram_name': 'https://instagram.com/users/artistv2',
            'soundcloud_page': 'https://soundcloud.com/users/artistv2',
            'youtube_channel': 'https://www.youtube.com/users/artistv2',
            'spotify_id': '7dGJo4pcD2V6oG8kP0tJRR',
            'apple_id': 'artistv2@example.com',
        }
        self.serializer = ArtistSerializer(
            data=self.data, context={'request': mocked_request}
        )

    def test_artist_serializer_data(self):
        self.assertTrue(self.serializer.is_valid())
        self.assertEqual(self.serializer.validated_data, self.data)

    @responses.activate
    @patch('amuse.api.v4.serializers.artist.fetch_spotify_image', return_value=None)
    def test_create_artist(self, mock_patch):
        self.serializer.is_valid()
        artist = self.serializer.save()
        self.assertEqual(artist.name, self.data['name'])
        self.assertEqual(artist.spotify_page, self.data['spotify_page'])
        self.assertEqual(artist.twitter_name, self.data['twitter_name'])
        self.assertEqual(artist.facebook_page, self.data['facebook_page'])
        self.assertEqual(artist.instagram_name, self.data['instagram_name'])
        self.assertEqual(artist.soundcloud_page, self.data['soundcloud_page'])
        self.assertEqual(artist.youtube_channel, self.data['youtube_channel'])
        self.assertEqual(artist.spotify_id, self.data['spotify_id'])
        self.assertEqual(artist.apple_id, self.data['apple_id'])
        self.assertTrue(artist.has_owner)
        self.assertIsNotNone(artist.id)
        self.assertIsNotNone(artist.created)
        mock_patch.assert_called_once()


@override_settings(**ZENDESK_MOCK_API_URL_TOKEN)
class TestArtistSearchSerializer(TestCase):
    @responses.activate
    def test_artist_to_representation_doesnt_return_social_links(self):
        add_zendesk_mock_post_response()

        serializer = ArtistSearchSerializer()
        artist = Artistv2Factory()
        response_data = serializer.to_representation(instance=artist)

        self.assertEqual(artist.id, response_data['id'])
        self.assertEqual(artist.name, response_data['name'])
        self.assertEqual(artist.spotify_id, response_data['spotify_id'])
        self.assertEqual(artist.apple_id, response_data['apple_id'])
        self.assertTrue(artist.has_owner)
        self.assertEqual(
            artist.created.strftime('%Y-%m-%dT%H:%M:%S.%fZ'), response_data['created']
        )
        self.assertEqual(artist.spotify_image, response_data['spotify_image'])

        # Making sure that all the social links are not in the response data.
        self.assertNotIn('spotify_page', response_data)
        self.assertNotIn('twitter_name', response_data)
        self.assertNotIn('facebook_page', response_data)
        self.assertNotIn('instagram_name', response_data)
        self.assertNotIn('soundcloud_page', response_data)
        self.assertNotIn('youtube_channel', response_data)


class TestContibutorArtistSerializer(TestCase):
    def setUp(self):
        self.data = {'name': 'Test Artist', 'spotify_id': '7dGJo4pcD2V6oG8kP0tJRR'}
        user = UserFactory()
        mocked_request = Mock(user=user)
        self.serializer = ContibutorArtistSerializer(
            data=self.data, context={'request': mocked_request}
        )

    def test_artist_serializer_data(self):
        self.assertTrue(self.serializer.is_valid())
        self.assertEqual(self.serializer.validated_data, self.data)

    def test_create_artist(self):
        self.serializer.is_valid()
        artist = self.serializer.save()
        self.assertEqual(artist.name, self.data['name'])
        self.assertIsNone(artist.spotify_page)
        self.assertIsNone(artist.twitter_name)
        self.assertIsNone(artist.facebook_page)
        self.assertIsNone(artist.instagram_name)
        self.assertIsNone(artist.soundcloud_page)
        self.assertIsNone(artist.youtube_channel)
        self.assertEqual(artist.spotify_id, self.data['spotify_id'])
        self.assertIsNone(artist.apple_id)
        self.assertFalse(artist.has_owner)
        self.assertIsNotNone(artist.id)
        self.assertIsNotNone(artist.created)

    def test_artist_to_representation(self):
        serializer = ContibutorArtistSerializer()
        artist = Artistv2Factory(owner=None)
        response_data = serializer.to_representation(instance=artist)

        self.assertEqual(artist.id, response_data['id'])
        self.assertEqual(artist.name, response_data['name'])
        self.assertEqual(artist.spotify_id, response_data['spotify_id'])
        self.assertFalse(artist.has_owner)

        # Making sure that the unnecessary field are not in the response data.
        self.assertNotIn('created', response_data)
        self.assertNotIn('apple_id', response_data)
        self.assertNotIn('spotify_page', response_data)
        self.assertNotIn('twitter_name', response_data)
        self.assertNotIn('facebook_page', response_data)
        self.assertNotIn('instagram_name', response_data)
        self.assertNotIn('soundcloud_page', response_data)
        self.assertNotIn('youtube_channel', response_data)
