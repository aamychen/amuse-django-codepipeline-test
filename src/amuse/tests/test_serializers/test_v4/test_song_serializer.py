from decimal import Decimal
from unittest.mock import Mock

from django.test import TestCase, override_settings
from django.utils import timezone
import responses

from amuse.api.v4.serializers.helpers import get_serialized_royalty_splits
from amuse.api.v4.serializers.song import SongSerializer
from amuse.tests.helpers import (
    ZENDESK_MOCK_API_URL_TOKEN,
    add_zendesk_mock_post_response,
)
from releases.models import RoyaltySplit
from releases.models.song import Song
from releases.tests.factories import GenreFactory, RoyaltySplitFactory, SongFactory
from subscriptions.tests.factories import SubscriptionFactory
from users.tests.factories import Artistv2Factory, UserFactory


@override_settings(**ZENDESK_MOCK_API_URL_TOKEN)
class TestSongSerializer(TestCase):
    @responses.activate
    def setUp(self):
        add_zendesk_mock_post_response()
        mocked_request = Mock()
        factory = GenreFactory()
        user_1 = UserFactory()
        user_2 = UserFactory()
        user_3 = UserFactory()
        user_4 = UserFactory()

        artist_1 = Artistv2Factory(owner=user_1)
        artist_2 = Artistv2Factory(owner=user_2)
        artist_3 = Artistv2Factory(owner=user_3)
        artist_4 = Artistv2Factory(owner=user_4)

        explicit_clean_string_value = Song.EXPLICIT_CHOICES[2][1]
        youtube_content_id_string_value = Song.YT_CONTENT_ID_CHOICES[0][1]
        origin_remix_string_value = Song.ORIGIN_CHOICES[2][1]

        self.data = {
            'name': 'Test Song 1',
            'sequence': 1,
            'version': 'Version Title',
            'explicit': explicit_clean_string_value,
            'recording_year': 2018,
            'original_release_date': '2020-10-10',
            'filename': 'users_filename.wav',
            'origin': origin_remix_string_value,
            'isrc': 'QZBJV1847115',
            'audio_s3_key': 'wave.wav',
            'youtube_content_id': youtube_content_id_string_value,
            'genre': {'id': factory.id, 'name': 'Genre'},
            'artists_roles': [
                {'roles': ['mixer'], 'artist_id': artist_2.id},
                {'roles': ['primary_artist'], 'artist_id': artist_1.id},
                {'roles': ['featured_artist'], 'artist_id': artist_3.id},
                {'roles': ['writer', 'producer'], 'artist_id': artist_4.id},
            ],
            'royalty_splits': [
                {'user_id': user_1.id, 'rate': 0.2},
                {'user_id': user_2.id, 'rate': 0.6},
                {'user_id': user_3.id, 'rate': 0.1},
                {'user_id': user_4.id, 'rate': 0.1},
            ],
        }
        self.serializer = SongSerializer(
            data=self.data, context={'request': mocked_request}
        )

        self.expected_error_message = (
            "The sum of the royalty splits' rates is not equal to 1"
        )

        self.user_1 = user_1
        self.user_2 = user_2
        self.artist_1 = artist_1

    def test_song_serializer_data(self):
        self.assertTrue(self.serializer.is_valid())
        self.assertEqual(self.serializer.validated_data['name'], self.data['name'])
        self.assertEqual(
            self.serializer.validated_data['sequence'], self.data['sequence']
        )
        self.assertEqual(
            self.serializer.validated_data['version'], self.data['version']
        )
        self.assertEqual(
            self.serializer.validated_data['explicit'], Song.EXPLICIT_CLEAN
        )
        self.assertEqual(
            self.serializer.validated_data['recording_year'],
            self.data['recording_year'],
        )
        self.assertEqual(
            self.serializer.validated_data['original_release_date'].strftime(
                '%Y-%m-%d'
            ),
            self.data['original_release_date'],
        )
        self.assertEqual(
            self.serializer.validated_data['filename'], self.data['filename']
        )
        self.assertEqual(self.serializer.validated_data['origin'], Song.ORIGIN_REMIX)
        self.assertEqual(self.serializer.validated_data['isrc'], self.data['isrc'])
        self.assertEqual(
            self.serializer.validated_data['youtube_content_id'],
            Song.YT_CONTENT_ID_NONE,
        )
        self.assertEqual(self.serializer.validated_data['genre'], self.data['genre'])
        self.assertEqual(
            self.serializer.validated_data['artists_roles'], self.data['artists_roles']
        )

        for index, royalty_split in enumerate(
            self.serializer.validated_data['royalty_splits']
        ):
            user_id = self.data['royalty_splits'][index]['user_id']
            rate = Decimal(self.data['royalty_splits'][index]['rate'])

            self.assertEqual(royalty_split['user_id'], user_id)
            self.assertEqual(royalty_split['rate'], round(rate, 4))

    def test_royalty_splits_total_rate_less_than_one(self):
        # Decrease royalty_split rate from 0.2 to 0.1 for the first artist.
        self.data['royalty_splits'][0]['rate'] = 0.1

        self.assertFalse(self.serializer.is_valid())
        self.assertIn('royalty_splits', self.serializer.errors)
        returned_error_message = str(self.serializer.errors['royalty_splits'][0])
        self.assertEqual(returned_error_message, self.expected_error_message)

    def test_royalty_splits_total_rate_greater_than_one(self):
        # Increase royalty_split rate from 0.2 to 0.5 for the first artist.
        self.data['royalty_splits'][0]['rate'] = 0.5
        self.assertFalse(self.serializer.is_valid())
        self.assertIn('royalty_splits', self.serializer.errors)
        returned_error_message = str(self.serializer.errors['royalty_splits'][0])
        self.assertEqual(returned_error_message, self.expected_error_message)

    def test_royalty_splits_duplicate_user_is_invalid(self):
        self.data["royalty_splits"] = [
            {"user_id": self.user_1.id, "rate": 0.4},
            {"user_id": self.user_1.id, "rate": 0.4},
            {"user_id": self.user_2.id, "rate": 0.2},
        ]
        self.assertFalse(self.serializer.is_valid())

    @responses.activate
    def test_to_representation_method_returns_royalty_splits(self):
        add_zendesk_mock_post_response()
        song = SongFactory()
        RoyaltySplitFactory(
            song=song,
            start_date=timezone.now().today(),
            rate=1.0,
            status=RoyaltySplit.STATUS_ACTIVE,
        )

        self.assertEqual(
            self.serializer.to_representation(song)['royalty_splits'],
            get_serialized_royalty_splits(song),
        )

    def test_validate_youtube_content_id_monetize_allowed_for_free_user(self):
        self.data['youtube_content_id'] = 'monetize'
        self.data['artist_id'] = self.artist_1.pk
        self.data['royalty_splits'] = [{'user_id': self.user_1.id, 'rate': 1.0}]
        mock_request = Mock(user=self.user_1, data=self.data)

        serializer = SongSerializer(data=self.data, context={'request': mock_request})

        self.assertFalse(self.user_1.is_pro)
        self.assertTrue(serializer.is_valid())

    def test_validate_youtube_content_id_monetize_allowed_for_pro(self):
        SubscriptionFactory(user=self.user_1)
        self.data['youtube_content_id'] = 'monetize'
        self.data['artist_id'] = self.artist_1.pk
        mock_request = Mock(user=self.user_1, data=self.data)

        serializer = SongSerializer(data=self.data, context={'request': mock_request})

        self.assertTrue(self.user_1.is_pro)
        self.assertTrue(serializer.is_valid())
