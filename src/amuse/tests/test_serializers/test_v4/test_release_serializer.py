from datetime import timedelta
from unittest.mock import Mock, patch

import responses
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.exceptions import ErrorDetail

from amuse.platform import PlatformType
from amuse.api.v4.serializers.release import ReleaseSerializer
from amuse.tests.helpers import (
    ZENDESK_MOCK_API_URL_TOKEN,
    add_zendesk_mock_post_response,
)
from countries.tests.factories import CountryFactory
from releases.models import Release, Song, SongArtistRole, Store
from releases.tests.factories import (
    GenreFactory,
    StoreFactory,
    ReleaseFactory,
    SongFactory,
)
from users.tests.factories import Artistv2Factory, UserFactory


@override_settings(**ZENDESK_MOCK_API_URL_TOKEN)
class TestReleaseSerializer(TestCase):
    @responses.activate
    def setUp(self):
        add_zendesk_mock_post_response()
        self.yt_cid_store = StoreFactory(
            is_pro=True, name=Store.YOUTUBE_CONTENT_ID_STORE_NAME
        )
        self.acrcloud = StoreFactory(
            name='acrcloud', internal_name='acrcloud', active=False
        )
        self.yt_music_store = StoreFactory(internal_name='youtube_music')
        self.genre = GenreFactory()
        self.user_1 = UserFactory(is_pro=True)
        self.user_2 = UserFactory()
        user_3 = UserFactory()
        user_4 = UserFactory()

        self.artist_1 = Artistv2Factory(owner=self.user_1)
        artist_2 = Artistv2Factory(owner=self.user_2)
        artist_3 = Artistv2Factory(owner=user_3)
        artist_4 = Artistv2Factory(owner=user_4)

        country_1 = CountryFactory()
        country_2 = CountryFactory()

        self.mocked_request = Mock(user=self.user_1)

        explicit_clean_string_value = Song.EXPLICIT_CHOICES[2][1]
        youtube_content_id_string_value = Song.YT_CONTENT_ID_CHOICES[0][1]
        origin_remix_string_value = Song.ORIGIN_CHOICES[2][1]
        release_date = timezone.now().date() + timedelta(days=30)

        self.data = {
            'artist_id': self.artist_1.id,
            'name': 'Postman Release (v4)',
            'label': None,
            'cover_art_filename': 'cover.jpg',
            'release_date': release_date.strftime('%Y-%m-%d'),
            'release_version': 'Release Version',
            'excluded_stores': [],
            'excluded_countries': [country_1.code, country_2.code],
            'songs': [
                {
                    'name': 'Test Release 1',
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
                    'genre': {'id': self.genre.id, 'name': self.genre.name},
                    'artists_roles': [
                        {'roles': ['mixer'], 'artist_id': artist_2.id},
                        {'roles': ['primary_artist'], 'artist_id': self.artist_1.id},
                        {'roles': ['featured_artist'], 'artist_id': artist_3.id},
                        {'roles': ['writer', 'producer'], 'artist_id': artist_4.id},
                    ],
                    'royalty_splits': [
                        {'user_id': self.user_1.id, 'rate': 0.2},
                        {'user_id': self.user_2.id, 'rate': 0.6},
                        {'user_id': user_3.id, 'rate': 0.1},
                        {'user_id': user_4.id, 'rate': 0.1},
                    ],
                }
            ],
        }

        self.serializer = ReleaseSerializer(
            data=self.data, context={'request': self.mocked_request}
        )

    def _create_songs(self, nr=3):
        return [
            {
                'name': 'Test Release 1',
                'sequence': i,
                'version': 'Version Title',
                'explicit': "clean",
                'recording_year': 2018,
                'original_release_date': '2020-10-10',
                'filename': 'users_filename.wav',
                'origin': "original",
                'isrc': f'QZBJV184711{i}',
                'audio_s3_key': 'wave.wav',
                'youtube_content_id': "none",
                'genre': {'id': self.genre.id, 'name': self.genre.name},
                'artists_roles': [
                    {'roles': ['primary_artist'], 'artist_id': self.artist_1.id}
                ],
                'royalty_splits': [{'user_id': self.user_1.id, 'rate': 1.0}],
            }
            for i in range(nr)
        ]

    def test_tencent_netease_are_included_when_no_explicit_tracks(self):
        store_1 = StoreFactory(name="Tencent", internal_name="tencent", active=True)
        store_2 = StoreFactory(name="NetEase", internal_name="netease", active=True)
        serializer = ReleaseSerializer(
            data=self.data, context={'request': self.mocked_request}
        )

        self.assertTrue(serializer.is_valid())
        self.assertNotIn(store_1.pk, serializer.validated_data["excluded_store_ids"])
        self.assertNotIn(store_2.pk, serializer.validated_data["excluded_store_ids"])

    def test_tencent_netease_are_excluded_when_explicit_tracks(self):
        self.data["songs"][0]["explicit"] = "explicit"
        store_1 = StoreFactory(name="Tencent", internal_name="tencent", active=True)
        store_2 = StoreFactory(name="NetEase", internal_name="netease", active=True)
        serializer = ReleaseSerializer(
            data=self.data, context={'request': self.mocked_request}
        )

        self.assertTrue(serializer.is_valid())
        self.assertIn(store_1.pk, serializer.validated_data["excluded_store_ids"])
        self.assertIn(store_2.pk, serializer.validated_data["excluded_store_ids"])

    def test_excluding_all_stores_sets_free_stores_for_free_user(self):
        store_1 = StoreFactory(name="Spotify")
        store_2 = StoreFactory(name="Tiktok", active=False)
        self.data["excluded_stores"] = [
            self.yt_cid_store.pk,
            store_1.pk,
            self.yt_music_store.pk,
        ]
        self.serializer = ReleaseSerializer(
            data=self.data, context={'request': self.mocked_request}
        )
        self.serializer.context['request'].user = self.user_2

        self.assertTrue(self.serializer.is_valid())
        self.assertEqual(
            self.serializer.validated_data['excluded_store_ids'], [self.yt_cid_store.pk]
        )

    def test_song_converts_0_based_to_1_based_sequence(self):
        self.data["songs"] = self._create_songs()
        self.serializer = ReleaseSerializer(
            data=self.data, context={'request': self.mocked_request}
        )
        self.assertTrue(self.serializer.is_valid())
        self.assertEqual(self.serializer.validated_data['songs'][0]["sequence"], 1)
        self.assertEqual(self.serializer.validated_data['songs'][1]["sequence"], 2)
        self.assertEqual(self.serializer.validated_data['songs'][2]["sequence"], 3)

    def test_release_serializer_data(self):
        self.assertTrue(self.serializer.is_valid())
        self.assertEqual(self.serializer.validated_data['name'], self.data['name'])
        self.assertEqual(self.serializer.validated_data['label'], self.data['label'])
        self.assertEqual(
            self.serializer.validated_data['cover_art_filename'],
            self.data['cover_art_filename'],
        )
        self.assertEqual(
            self.serializer.validated_data['release_date'].strftime('%Y-%m-%d'),
            self.data['release_date'],
        )
        self.assertEqual(
            self.serializer.validated_data['release_version'],
            self.data['release_version'],
        )
        self.assertEqual(
            self.serializer.validated_data['excluded_store_ids'],
            self.data['excluded_stores'],
        )
        self.assertEqual(
            self.serializer.validated_data['excluded_country_codes'],
            self.data['excluded_countries'],
        )
        self.assertEqual(
            self.serializer.validated_data['songs'][0]['sequence'],
            self.data['songs'][0]['sequence'],
        )
        self.assertEqual(
            self.serializer.validated_data['songs'][0]['version'],
            self.data['songs'][0]['version'],
        )
        self.assertEqual(
            self.serializer.validated_data['songs'][0]['explicit'], Song.EXPLICIT_CLEAN
        )
        self.assertEqual(
            self.serializer.validated_data['songs'][0]['recording_year'],
            self.data['songs'][0]['recording_year'],
        )
        self.assertEqual(
            self.serializer.validated_data['songs'][0][
                'original_release_date'
            ].strftime('%Y-%m-%d'),
            self.data['songs'][0]['original_release_date'],
        )
        self.assertEqual(
            self.serializer.validated_data['songs'][0]['filename'],
            self.data['songs'][0]['filename'],
        )
        self.assertEqual(
            self.serializer.validated_data['songs'][0]['origin'], Song.ORIGIN_REMIX
        )
        self.assertEqual(
            self.serializer.validated_data['songs'][0]['isrc'],
            self.data['songs'][0]['isrc'],
        )
        self.assertEqual(
            self.serializer.validated_data['songs'][0]['youtube_content_id'],
            Song.YT_CONTENT_ID_NONE,
        )
        self.assertEqual(
            self.serializer.validated_data['songs'][0]['genre'],
            self.data['songs'][0]['genre'],
        )
        self.assertEqual(
            self.serializer.validated_data['songs'][0]['artists_roles'],
            self.data['songs'][0]['artists_roles'],
        )

    @patch(
        'amuse.platform.PlatformHelper.from_request', return_value=PlatformType.UNKNOWN
    )
    @patch('amuse.api.v4.serializers.release.event_created')
    @patch('releases.utils.tasks')
    def test_create_release_data(self, mocked_tasks, mocked_event_created, _):
        self.acrcloud.admin_active = True
        self.acrcloud.save()
        add_zendesk_mock_post_response()
        self.serializer.is_valid()
        release = self.serializer.save()
        self.assertEqual(release.name, self.data['name'])
        self.assertEqual(release.label, self.data['label'])
        self.assertEqual(release.cover_art.file.name, self.data['cover_art_filename'])
        self.assertEqual(
            release.release_date.strftime('%Y-%m-%d'), self.data['release_date']
        )
        self.assertTrue(self.acrcloud.admin_active)
        self.assertTrue(self.acrcloud in release.stores.all())

        self.assertEqual(
            sorted([store for store in release.excluded_store_ids]),
            sorted(self.data['excluded_stores']),
        )
        self.assertEqual(
            sorted([country_code for country_code in release.excluded_country_codes]),
            sorted(self.data['excluded_countries']),
        )
        song = release.songs.first()
        self.assertEqual(song.sequence, self.data['songs'][0]['sequence'])
        self.assertEqual(song.version, self.data['songs'][0]['version'])
        self.assertEqual(song.explicit, Song.EXPLICIT_CLEAN)
        self.assertEqual(song.recording_year, self.data['songs'][0]['recording_year'])
        self.assertEqual(
            song.original_release_date.strftime('%Y-%m-%d'),
            self.data['songs'][0]['original_release_date'],
        )
        self.assertEqual(song.filename, self.data['songs'][0]['filename'])
        self.assertEqual(song.origin, Song.ORIGIN_REMIX)
        self.assertEqual(song.isrc_code, self.data['songs'][0]['isrc'])
        self.assertEqual(song.youtube_content_id, Song.YT_CONTENT_ID_NONE)
        self.assertEqual(
            {'id': song.genre.id, 'name': song.genre.name},
            self.data['songs'][0]['genre'],
        )
        artists_roles = self.data['songs'][0]['artists_roles']

        for artist_roles in artists_roles:
            artist_id = artist_roles['artist_id']
            roles = artist_roles['roles']
            for role in roles:
                # Make sure a SongArtistRole is created
                self.assertTrue(
                    song.songartistrole_set.filter(
                        artist_id=artist_id,
                        role=SongArtistRole.get_role_for_keyword(role),
                    ).exists()
                )
                # Make sure a SongArtistRole created only one instance
                self.assertEqual(
                    song.songartistrole_set.filter(
                        artist_id=artist_id,
                        role=SongArtistRole.get_role_for_keyword(role),
                    ).count(),
                    1,
                )

    @patch(
        'amuse.platform.PlatformHelper.from_request', return_value=PlatformType.UNKNOWN
    )
    @patch('amuse.api.v4.serializers.release.event_created')
    @patch('releases.utils.tasks')
    def test_create_release_data_exclude_acrcloud(
        self, mocked_tasks, mocked_event_created, _
    ):
        self.acrcloud.admin_active = False
        self.acrcloud.save()
        add_zendesk_mock_post_response()
        self.serializer.is_valid()
        release = self.serializer.save()
        self.assertFalse(self.acrcloud.admin_active)
        self.assertFalse(self.acrcloud in release.stores.all())

    @patch(
        'amuse.platform.PlatformHelper.from_request', return_value=PlatformType.UNKNOWN
    )
    @patch('amuse.api.v4.serializers.release.event_created')
    @patch('releases.utils.tasks')
    def test_tasks_called_when_create_release(
        self, mocked_tasks, mocked_event_created, _
    ):
        add_zendesk_mock_post_response()
        self.serializer.is_valid()
        release = self.serializer.save()
        audio_s3_key = self.data['songs'][0]['audio_s3_key']
        song = release.songs.first()
        mocked_tasks.transcode.assert_called_once_with(audio_s3_key, song.id)
        mocked_tasks.audio_recognition.assert_called_once_with(audio_s3_key, song.id)

    @patch(
        'amuse.platform.PlatformHelper.from_request', return_value=PlatformType.UNKNOWN
    )
    @patch('amuse.api.v4.serializers.release.event_created')
    @patch('releases.utils.tasks')
    def test_event_created_called_when_create_release(
        self, mocked_tasks, mocked_event_created, _
    ):
        add_zendesk_mock_post_response()
        self.serializer.is_valid()
        release = self.serializer.save()
        mocked_event_created.assert_called_once_with(
            self.serializer.context['request'], release
        )

    @responses.activate
    def test_release_royalty_splits_rates_total_not_equal_to_one(self):
        # Increase royalty_split rate from 0.2 to 0.5 for the first artist.
        self.data['songs'][0]['royalty_splits'][0]['rate'] = 0.5
        self.assertFalse(self.serializer.is_valid())

        expected_error_message = (
            "The sum of the royalty splits' rates is not equal to 1"
        )

        self.assertIn('songs', self.serializer.errors)
        self.assertIn('royalty_splits', self.serializer.errors['songs'][0])

        returned_error_message = str(
            self.serializer.errors['songs'][0]['royalty_splits'][0]
        )
        self.assertEqual(returned_error_message, expected_error_message)

    @patch(
        'amuse.platform.PlatformHelper.from_request', return_value=PlatformType.UNKNOWN
    )
    @patch('amuse.api.v4.serializers.release.event_created')
    @patch('releases.utils.tasks')
    def test_monetized_song_adds_youtube_content_id_store(
        self, mocked_tasks, mocked_event_created, _
    ):
        store = Store.get_yt_content_id_store()
        yt_content_id_store_id = store.pk
        self.data['songs'][0]['youtube_content_id'] = 'monetize'
        self.data['excluded_stores'] = [yt_content_id_store_id]

        serializer = ReleaseSerializer(
            data=self.data, context={'request': self.mocked_request}
        )
        self.assertTrue(serializer.is_valid())
        release = serializer.save()

        self.assertNotIn(yt_content_id_store_id, release.excluded_store_ids)
        self.assertIn(store, release.stores.all())

    @patch(
        'amuse.platform.PlatformHelper.from_request', return_value=PlatformType.UNKNOWN
    )
    @patch('amuse.api.v4.serializers.release.event_created')
    @patch('releases.utils.tasks')
    def test_non_monetized_song_does_not_add_youtube_content_id_store(
        self, mocked_tasks, mocked_event_created, _
    ):
        yt_content_id_store_id = Store.get_yt_content_id_store().pk
        self.data['excluded_stores'] = [yt_content_id_store_id]

        serializer = ReleaseSerializer(
            data=self.data, context={'request': self.mocked_request}
        )
        self.assertTrue(serializer.is_valid())
        release = serializer.save()

        self.assertIn(Store.get_yt_content_id_store().pk, release.excluded_store_ids)

    @patch(
        'amuse.platform.PlatformHelper.from_request', return_value=PlatformType.UNKNOWN
    )
    @patch('amuse.api.v4.serializers.release.event_created')
    @patch('releases.utils.tasks')
    def test_monetized_song_excluded_yt_content_id_store_and_yt_music_store(
        self, _, __, ___
    ):
        store = Store.get_yt_content_id_store()
        yt_content_id_store_id = store.pk
        self.data['songs'][0]['youtube_content_id'] = 'monetize'
        self.data['excluded_stores'] = [self.yt_music_store.pk, yt_content_id_store_id]

        serializer = ReleaseSerializer(
            data=self.data, context={'request': self.mocked_request}
        )

        self.assertTrue(serializer.is_valid())
        release = serializer.save()

        self.assertIn(self.yt_music_store.pk, release.excluded_store_ids)
        self.assertIn(yt_content_id_store_id, release.excluded_store_ids)
        self.assertNotIn(self.yt_music_store, release.stores.all())
        self.assertNotIn(yt_content_id_store_id, release.stores.all())

    @patch(
        'amuse.platform.PlatformHelper.from_request', return_value=PlatformType.UNKNOWN
    )
    @patch('amuse.api.v4.serializers.release.event_created')
    @patch('releases.utils.tasks')
    def test_monetized_song_excluded_yt_content_id_store_and_yt_music_store_free_user(
        self, mocked_tasks, mocked_event_created, _
    ):
        store = Store.get_yt_content_id_store()
        StoreFactory(name='another store')
        yt_content_id_store_id = store.pk
        self.data['songs'][0]['youtube_content_id'] = 'monetize'
        self.data['excluded_stores'] = [self.yt_music_store.pk, yt_content_id_store_id]

        serializer = ReleaseSerializer(
            data=self.data, context={'request': self.mocked_request}
        )

        self.serializer.context['request'].user = self.user_2

        self.assertTrue(serializer.is_valid())
        release = serializer.save()

        self.assertIn(self.yt_music_store.pk, release.excluded_store_ids)
        self.assertIn(yt_content_id_store_id, release.excluded_store_ids)
        self.assertNotIn(self.yt_music_store, release.stores.all())
        self.assertNotIn(yt_content_id_store_id, release.stores.all())

    @patch(
        'amuse.platform.PlatformHelper.from_request', return_value=PlatformType.UNKNOWN
    )
    @patch('amuse.api.v4.serializers.release.event_created')
    @patch('releases.utils.tasks')
    def test_is_first_time_cid_use_true(self, mocked_tasks, mocked_event_created, _):
        self.data['songs'][0]['youtube_content_id'] = 'monetize'

        serializer = ReleaseSerializer(
            data=self.data, context={'request': self.mocked_request}
        )
        serializer.context['request'].user = self.user_1

        self.assertTrue(serializer.is_valid())
        new_release = serializer.save()
        is_first_time_cid_use = serializer._is_first_time_cid_use(
            self.user_1, new_release
        )

        self.assertTrue(is_first_time_cid_use)

    @patch(
        'amuse.platform.PlatformHelper.from_request', return_value=PlatformType.UNKNOWN
    )
    @patch('amuse.api.v4.serializers.release.event_created')
    @patch('releases.utils.tasks')
    def test_is_first_time_cid_use_false_existing_release_monetized(
        self, mocked_tasks, mocked_event_created, _
    ):
        existing_release = ReleaseFactory(created_by=self.user_1)
        SongFactory(
            release=existing_release, youtube_content_id=Song.YT_CONTENT_ID_MONETIZE
        )

        self.data['songs'][0]['youtube_content_id'] = 'monetize'

        serializer = ReleaseSerializer(
            data=self.data, context={'request': self.mocked_request}
        )
        serializer.context['request'].user = self.user_1

        self.assertTrue(serializer.is_valid())
        new_release = serializer.save()
        is_first_time_cid_use = serializer._is_first_time_cid_use(
            self.user_1, new_release
        )

        self.assertFalse(is_first_time_cid_use)

    @patch(
        'amuse.platform.PlatformHelper.from_request', return_value=PlatformType.UNKNOWN
    )
    @patch('amuse.api.v4.serializers.release.event_created')
    @patch('releases.utils.tasks')
    def test_is_first_time_cid_use_true_existing_release_non_monetized(
        self, mocked_tasks, mocked_event_created, _
    ):
        existing_release = ReleaseFactory(created_by=self.user_1)
        SongFactory(release=existing_release)

        self.data['songs'][0]['youtube_content_id'] = 'monetize'

        serializer = ReleaseSerializer(
            data=self.data, context={'request': self.mocked_request}
        )
        serializer.context['request'].user = self.user_1

        self.assertTrue(serializer.is_valid())
        new_release = serializer.save()
        is_first_time_cid_use = serializer._is_first_time_cid_use(
            self.user_1, new_release
        )

        self.assertTrue(is_first_time_cid_use)

    @patch(
        'amuse.platform.PlatformHelper.from_request', return_value=PlatformType.UNKNOWN
    )
    @patch('amuse.api.v4.serializers.release.event_created')
    @patch('releases.utils.tasks')
    def test_is_first_time_cid_use_false_new_release_non_monetized(
        self, mocked_tasks, mocked_event_created, _
    ):
        existing_release = ReleaseFactory(created_by=self.user_1)
        SongFactory(release=existing_release)

        serializer = ReleaseSerializer(
            data=self.data, context={'request': self.mocked_request}
        )
        serializer.context['request'].user = self.user_1

        self.assertTrue(serializer.is_valid())
        new_release = serializer.save()
        is_first_time_cid_use = serializer._is_first_time_cid_use(
            self.user_1, new_release
        )

        self.assertFalse(is_first_time_cid_use)
