import copy
from datetime import timedelta, datetime
import json
from unittest import mock, skip
from uuid import uuid4

import pytest
from django.conf import settings
from django.urls import reverse_lazy as reverse
from django.utils import timezone
import responses
from freezegun import freeze_time
from rest_framework import exceptions, status
from waffle.models import Switch

from amuse.api.v4.serializers.release import ReleaseSerializer
from amuse.models import Transcoding
from amuse.models.event import Event
from amuse.storages import S3Storage
from amuse.tests.helpers import build_auth_header
from amuse.tests.test_api.base import API_V4_ACCEPT_VALUE, AmuseAPITestCase
from codes.models import Code
from codes.tests.factories import ISRCFactory, MetadataLanguageFactory, UPCFactory
from countries.tests.factories import CountryFactory
from releases.models import Release, RoyaltySplit, Song, SongArtistRole, SongFile, Store
from releases.models.release import ReleaseArtistRole
from releases.tests.factories import (
    CoverArtFactory,
    GenreFactory,
    ReleaseFactory,
    SongFactory,
    StoreFactory,
)
from subscriptions.models import Subscription
from users.models import ArtistV2, SongArtistInvitation, User, UserArtistRole
from users.tests.factories import Artistv2Factory, UserFactory
from django.core.cache import cache


class ReleaseAPITestCase(AmuseAPITestCase):
    def setUp(self):
        super(ReleaseAPITestCase, self).setUp()
        StoreFactory(internal_name='youtube_music')
        self.user = UserFactory(artist_name='Lil Artist', is_pro=True)
        self.user_2 = UserFactory()
        self.user_3 = UserFactory()
        self.user_4 = UserFactory()

        self.artist_1 = self.user.create_artist_v2(name='Lil Artist')
        self.artist_2 = self.user_2.create_artist_v2(name='FeaturedArtist')
        self.artist_3 = self.user_3.create_artist_v2(name='Writer Artist')
        self.artist_4 = self.user_4.create_artist_v2(name='ProducerdArtist')

        self.artists = dict()
        self.artists[self.artist_1.id] = self.artist_1
        self.artists[self.artist_2.id] = self.artist_2
        self.artists[self.artist_3.id] = self.artist_3
        self.artists[self.artist_4.id] = self.artist_4

        self.genre = GenreFactory()

        country_1 = CountryFactory()
        country_2 = CountryFactory()

        self.client.credentials(HTTP_ACCEPT=API_V4_ACCEPT_VALUE)
        self.client.force_authenticate(self.user)

        StoreFactory(name='Spotify')
        StoreFactory(is_pro=True, name=Store.YOUTUBE_CONTENT_ID_STORE_NAME)
        StoreFactory(
            name='Audiomack', internal_name='audiomack', active=True, is_pro=False
        )
        UPCFactory(status=Code.STATUS_UNUSED)
        self.isrc = ISRCFactory(status=Code.STATUS_UNUSED)
        genre = GenreFactory()

        cover_art_storage = S3Storage(
            bucket_name=settings.AWS_COVER_ART_UPLOADED_BUCKET_NAME
        )
        cover_filename = 'cover.jpg'
        with cover_art_storage.open(cover_filename, 'wb') as f:
            f.write(open('amuse/tests/test_api/data/amuse.jpg', 'rb').read())
        self.release_date = timezone.now().date() + timedelta(days=30)

        self.request_payload = {
            'name': 'Postman Release (v4)',
            'label': None,
            'cover_art_filename': 'cover.jpg',
            'schedule_type': Release.SCHEDULE_TYPES_MAP[Release.SCHEDULE_TYPE_STATIC],
            'release_date': self.release_date.strftime('%Y-%m-%d'),
            'excluded_stores': [],
            'excluded_countries': [country_1.code, country_2.code],
            'upc': '',
            'artist_id': self.artist_1.id,
            'songs': [
                {
                    'name': 'Test Song 1',
                    'sequence': 1,
                    'version': 'Version Title',
                    'explicit': 'clean',
                    'recording_year': 2018,
                    'filename': 'users_filename.wav',
                    'origin': 'remix',
                    'isrc': '',
                    'audio_s3_key': 'wave.wav',
                    'youtube_content_id': 'none',
                    'cover_licensor': '',
                    'genre': {'id': genre.id, 'name': genre.name},
                    'artists_roles': [
                        {'roles': ['mixer', 'writer'], 'artist_id': self.artist_3.id},
                        {'roles': ['primary_artist'], 'artist_id': self.artist_1.id},
                        {'roles': ['featured_artist'], 'artist_id': self.artist_2.id},
                        {'roles': ['producer'], 'artist_id': self.artist_4.id},
                    ],
                    'royalty_splits': [
                        {'user_id': self.user.id, 'rate': 0.5},
                        {'user_id': self.user_2.id, 'rate': 0.25},
                        {'user_id': self.user_3.id, 'rate': 0.05},
                        {'user_id': self.user_4.id, 'rate': 0.2},
                    ],
                },
                {
                    'name': 'Test Song 2',
                    'sequence': 2,
                    'version': '',
                    'explicit': 'none',
                    'recording_year': '1900',
                    'filename': '',
                    'origin': 'cover',
                    'isrc': 'TEST12345678',
                    'audio_s3_key': 'wave.wav',
                    'youtube_content_id': 'none',
                    'cover_licensor': '',
                    'genre': {'id': genre.id, 'name': genre.name},
                    'artists_roles': [
                        {'roles': ['primary_artist'], 'artist_id': self.artist_1.id},
                        {'roles': ['producer'], 'artist_id': self.artist_4.id},
                    ],
                    'royalty_splits': [
                        {'user_id': self.user.id, 'rate': 0.75},
                        {'user_id': self.user_4.id, 'rate': 0.25},
                    ],
                },
            ],
        }
        cache.clear()

    @responses.activate
    @mock.patch('releases.utils.tasks')
    def test_verify_fields_on_created_release(self, mocked_tasks):
        url = reverse('release-list')
        response = self.client.post(url, self.request_payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        expected_keys = [
            'cover_art',
            'error_flags',
            'excluded_countries',
            'excluded_stores',
            'genre',
            'id',
            'label',
            'name',
            'created',
            'original_release_date',
            'release_date',
            'release_version',
            'songs',
            'status',
            'type',
            'upc',
            'artist_roles',
            'user_id',
            'link',
            'include_pre_save_link',
            'schedule_type',
        ]

        expected_song_keys = [
            'artists_roles',
            'artists_invites',
            'cover_licensor',
            'error_flags',
            'explicit',
            'filename',
            'genre',
            'id',
            'isrc',
            'name',
            'origin',
            'original_release_date',
            'recording_year',
            'royalty_splits',
            'sequence',
            'version',
            'youtube_content_id',
            'preview_start_time',
        ]

        expected_cover_art_keys = ['id', 'file', 'filename', 'thumbnail', 'checksum']

        self.assertCountEqual(expected_keys, response.data.keys())
        self.assertCountEqual(expected_song_keys, response.data['songs'][0].keys())
        self.assertCountEqual(expected_song_keys, response.data['songs'][1].keys())
        self.assertCountEqual(
            expected_cover_art_keys, response.data['cover_art'].keys()
        )

    @responses.activate
    @mock.patch('releases.utils.tasks')
    def test_release_version_in_response(self, mocked_tasks):
        url = reverse('release-list')
        self.request_payload["release_version"] = "Release Version"
        response = self.client.post(url, self.request_payload, format='json')
        self.assertEqual(
            response.data["release_version"], self.request_payload["release_version"]
        )

    @responses.activate
    @mock.patch('releases.utils.tasks')
    def test_verify_artists_roles_data(self, mocked_tasks):
        url = reverse('release-list')
        response = self.client.post(url, self.request_payload, format='json')

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        def exists(item, actual_items):
            for actual in actual_items:
                if actual['artist_id'] != item['artist_id']:
                    continue

                if actual['artist_name'] != self.artists[item['artist_id']].name:
                    continue

                if len(actual['roles']) != len(item['roles']):
                    continue

                item['roles'].sort()
                actual['roles'].sort()

                if actual['roles'] == item['roles']:
                    return True

            return False

        # song0
        actual0 = response.data['songs'][0]['artists_roles']
        expected0 = self.request_payload['songs'][0]['artists_roles']

        for item in expected0:
            self.assertTrue(exists(item, actual0))

        # song1
        actual1 = response.data['songs'][1]['artists_roles']
        expected1 = self.request_payload['songs'][1]['artists_roles']

        for item in expected1:
            self.assertTrue(exists(item, actual1))

    @responses.activate
    @mock.patch('releases.utils.tasks')
    def test_verify_royalty_splits_data(self, mocked_tasks):
        url = reverse('release-list')
        response = self.client.post(url, self.request_payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        # Get royalty_splits from request_payload of the first song.
        request_royalty_splits = self.request_payload['songs'][0]['royalty_splits']
        # Get royalty_splits from response.data of the first song.
        response_royalty_splits = response.data['songs'][0]['royalty_splits']

        # Loop through all the request and response royalty_splits one at
        # the time.
        for request_royalty_split, response_royalty_split in zip(
            request_royalty_splits, response_royalty_splits
        ):
            # Get the expected user name from the user_id in the request.
            user = User.objects.get(id=request_royalty_split['user_id'])
            expected_name = user.name

            # Get the received user name in the response.
            received_name = response_royalty_split['name']

            # Get the expected rate in the request.
            expected_rate = request_royalty_split['rate']
            # Get the received user_id in the response.
            received_rate = response_royalty_split['rate']

            # Make sure we have the same user_id.
            self.assertEqual(received_name, expected_name)
            # Make sure we have the same rate.
            # Since Django Restful Framework convert DecimalField to string
            # we needed to convert it to float to match the expected value.
            self.assertEqual(float(received_rate), expected_rate)

    @responses.activate
    @mock.patch('releases.utils.tasks')
    def test_verify_created_release_data(self, mocked_tasks):
        url = reverse('release-list')

        response = self.client.post(url, self.request_payload, format='json')

        self.assertEqual(response.data['type'], 'single')
        self.assertIsNone(response.data['original_release_date'])
        self.assertIsNone(response.data['songs'][0]['original_release_date'])
        self.assertEqual(response.data['upc'], '-')

        release = Release.objects.get(pk=response.data['id'])
        self.assertEqual(release.type, Release.TYPE_SINGLE)

        self.assertEqual(
            Release.SCHEDULE_TYPES_MAP[Release.SCHEDULE_TYPE_STATIC],
            response.data['schedule_type'],
        )

    def test_coverart_checksum_in_response(self):
        release = ReleaseFactory(user=self.user)
        CoverArtFactory(release=release)
        url = reverse('release-list')

        response = self.client.get(url)
        release.cover_art.refresh_from_db()
        self.assertIn("checksum", response.data[0]["cover_art"])
        self.assertEqual(
            response.data[0]["cover_art"]["checksum"], release.cover_art.checksum
        )

    @responses.activate
    def test_release_cannot_be_created_with_email_not_verified(self):
        self.user.email_verified = False
        self.user.save()
        url = reverse('release-list')

        response = self.client.post(url, self.request_payload, format='json')

        error = exceptions.ErrorDetail(
            'Release cannot be created as long as email is not verified',
            code='permission_denied',
        )
        expected_error_response = {'detail': error}
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(response.data, expected_error_response)

    @responses.activate
    def test_create_royalty_split_with_not_existing_user_id_returns_400(self):
        self.user_4.id = 1_287_369_217_863_871
        self.user.save()

        self.request_payload['songs'][0]['royalty_splits'][3][
            'user_id'
        ] = self.user_4.id
        self.request_payload['songs'][1]['royalty_splits'][1][
            'user_id'
        ] = self.user_4.id

        url = reverse('release-list')

        response = self.client.post(url, self.request_payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    @responses.activate
    @mock.patch('releases.utils.tasks')
    def test_one_track_release_version_same_as_song_version(self, mocked_tasks):
        two_songs = self.request_payload['songs']
        self.request_payload['songs'] = two_songs[:1]

        url = reverse('release-list')
        response = self.client.post(url, self.request_payload, format='json')

        release = Release.objects.get(pk=response.data['id'])
        song = Song.objects.get(pk=response.data['songs'][0]['id'])
        self.assertEqual(release.release_version, song.version)

        self.request_payload['songs'] = two_songs

    @responses.activate
    @mock.patch('releases.utils.tasks')
    def test_creation_with_artist_id(self, mocked_tasks):
        artist = Artistv2Factory()
        UserArtistRole.objects.create(
            artist=artist, user=self.user, type=UserArtistRole.ADMIN
        )
        self.request_payload['artist_id'] = artist.id
        self.request_payload['songs'][0]['artists_roles'].append(
            {'artist_id': artist.id, 'roles': ['primary_artist']}
        )
        self.request_payload['songs'][1]['artists_roles'].append(
            {'artist_id': artist.id, 'roles': ['primary_artist']}
        )

        url = reverse('release-list')
        response = self.client.post(url, self.request_payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)

        release = Release.objects.last()
        rar = ReleaseArtistRole.objects.filter(
            release=release, role=ReleaseArtistRole.ROLE_PRIMARY_ARTIST
        )
        self.assertEqual(len(rar), 1)
        self.assertEqual(rar.first().artist, artist)
        self.assertEqual(rar.first().main_primary_artist, True)

    @responses.activate
    @mock.patch('releases.utils.tasks')
    def test_pre_save_link_disallowed_for_start_users(self, mocked_tasks):
        Subscription.objects.filter(user=self.user).delete()
        self.request_payload['include_pre_save_link'] = True

        url = reverse('release-list')
        response = self.client.post(url, self.request_payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        # if we don't request the pre-save link it will be set to false
        self.request_payload['include_pre_save_link'] = False
        response = self.client.post(url, self.request_payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        release = Release.objects.last()
        self.assertFalse(release.include_pre_save_link)

    @responses.activate
    @mock.patch('releases.utils.tasks')
    def test_pre_save_link_allowed_for_non_start_users(self, mocked_tasks):
        self.request_payload['include_pre_save_link'] = True
        url = reverse('release-list')
        response = self.client.post(url, self.request_payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        release = Release.objects.last()
        self.assertTrue(release.include_pre_save_link)

    @responses.activate
    @mock.patch('releases.utils.tasks')
    def test_pre_save_link_is_disabled_by_default(self, mocked_tasks):
        url = reverse('release-list')
        response = self.client.post(url, self.request_payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        release = Release.objects.last()
        self.assertFalse(release.include_pre_save_link)

    @responses.activate
    @mock.patch('releases.utils.tasks')
    def test_pre_save_link_is_disabled_for_asap_release(self, mocked_tasks):
        url = reverse('release-list')
        self.request_payload['schedule_type'] = Release.SCHEDULE_TYPES_MAP[
            Release.SCHEDULE_TYPE_ASAP
        ]
        self.request_payload['include_pre_save_link'] = True
        response = self.client.post(url, self.request_payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        release = Release.objects.last()
        self.assertFalse(release.include_pre_save_link)

    @responses.activate
    @mock.patch('releases.utils.tasks')
    def test_free_user_label_must_be_artist_name(self, mocked_tasks):
        Subscription.objects.filter(user=self.user).delete()
        for song in self.request_payload['songs']:
            song['royalty_splits'] = [{'user_id': self.user.id, 'rate': 1}]
        self.request_payload['label'] = 'Other artists name'

        url = reverse('release-list')
        response = self.client.post(url, self.request_payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        self.request_payload['label'] = self.artist_1.name
        response = self.client.post(url, self.request_payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    @responses.activate
    @mock.patch('releases.utils.tasks')
    def test_free_user_label_defaults_to_artist_name(self, mocked_tasks):
        Subscription.objects.filter(user=self.user).delete()
        for song in self.request_payload['songs']:
            song['royalty_splits'] = [{'user_id': self.user.id, 'rate': 1}]
        self.request_payload['label'] = None

        url = reverse('release-list')
        response = self.client.post(url, self.request_payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['label'], self.artist_1.name)

    @responses.activate
    @mock.patch('releases.utils.tasks')
    def test_frozen_user_cannot_create_release(self, mocked_tasks):
        self.user.is_frozen = True
        self.user.save()
        self.user.refresh_from_db()

        artist = Artistv2Factory()
        UserArtistRole.objects.create(
            artist=artist, user=self.user, type=UserArtistRole.OWNER
        )
        self.request_payload['artist_id'] = artist.id

        url = reverse('release-list')
        response = self.client.post(url, self.request_payload, format='json')
        self.assertEqual(status.HTTP_403_FORBIDDEN, response.status_code, response.data)

    @responses.activate
    @mock.patch('releases.utils.tasks')
    def test_spectator_cannot_create_release(self, mocked_tasks):
        artist = Artistv2Factory()
        UserArtistRole.objects.create(
            artist=artist, user=self.user, type=UserArtistRole.SPECTATOR
        )
        self.request_payload['artist_id'] = artist.id

        url = reverse('release-list')
        response = self.client.post(url, self.request_payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN, response.data)

    @responses.activate
    @mock.patch('releases.utils.tasks')
    def test_featured_artists_have_read_access_to_release(self, mocked_tasks):
        url = reverse('release-list')
        response = self.client.post(url, self.request_payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        release = Release.objects.last()

        self.client.force_authenticate(self.user_2)
        url = reverse('release-detail', args=[release.id])
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)

    @responses.activate
    @mock.patch('releases.utils.tasks')
    def test_featured_artists_dont_have_write_access_to_release(self, mocked_tasks):
        url = reverse('release-list')
        response = self.client.post(url, self.request_payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        release = Release.objects.last()

        self.client.force_authenticate(self.user_2)
        url = reverse('release-detail', args=[release.id])
        response = self.client.patch(url, data={'release_date': '2000-01-01'})
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN, response.data)

    @responses.activate
    @mock.patch('releases.utils.tasks')
    def test_multiple_artists_must_have_main_artist_selected(self, mocked_tasks):
        Subscription.objects.filter(user=self.user).delete()
        self.user.create_artist_v2(name='Lil Artist')

        url = reverse('release-list')
        response = self.client.post(url, self.request_payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN, response.data)

    @responses.activate
    @mock.patch('releases.utils.tasks')
    def test_artist_id_must_be_main_artist_profile(self, mocked_tasks):
        Subscription.objects.filter(user=self.user).delete()
        for song in self.request_payload['songs']:
            song['royalty_splits'] = [{'user_id': self.user.id, 'rate': 1}]

        artist2 = self.user.create_artist_v2(name='Lil Artist')
        self.user.userartistrole_set.filter(artist=self.artist_1).update(
            main_artist_profile=True
        )

        url = reverse('release-list')
        self.request_payload['artist_id'] = artist2.id
        response = self.client.post(url, self.request_payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN, response.data)

        self.request_payload['artist_id'] = self.artist_1.id
        response = self.client.post(url, self.request_payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)

    @responses.activate
    @mock.patch('releases.utils.tasks')
    def test_admin_can_create_even_if_owner_is_not_pro(self, mocked_tasks):
        Subscription.objects.filter(user=self.user).delete()
        for song in self.request_payload['songs']:
            song['royalty_splits'] = [{'user_id': self.user.id, 'rate': 1}]

        admin = UserFactory()
        UserArtistRole.objects.create(
            user=admin, artist=self.artist_1, type=UserArtistRole.ADMIN
        )
        self.client.force_authenticate(admin)

        url = reverse('release-list')
        response = self.client.post(url, self.request_payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)

    @responses.activate
    @mock.patch('releases.utils.tasks')
    def test_one_artist_teams_are_allowed(self, mocked_tasks):
        Subscription.objects.filter(user=self.user).delete()
        for song in self.request_payload['songs']:
            song['royalty_splits'] = [{'user_id': self.user.id, 'rate': 1}]

        url = reverse('release-list')
        self.request_payload['artist_id'] = self.artist_1.id
        response = self.client.post(url, self.request_payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)

    @responses.activate
    @mock.patch('releases.utils.tasks')
    def test_queryset_does_not_contain_duplicates(self, mocked_tasks):
        url = reverse('release-list')
        response = self.client.post(url, self.request_payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        response = self.client.get(url)
        self.assertEqual(len(response.data), 1, response.data)

    @responses.activate
    @mock.patch('releases.utils.tasks')
    def test_several_track_release_version_not_same_as_song_version(self, mocked_tasks):
        url = reverse('release-list')
        response = self.client.post(url, self.request_payload, format='json')

        release = Release.objects.get(pk=response.data['id'])
        song = Song.objects.get(pk=response.data['songs'][0]['id'])
        self.assertFalse(bool(release.release_version))
        self.assertNotEqual(release.release_version, song.version)

    @responses.activate
    def test_release_label_above_max_length_returns_validation_error(self):
        url = reverse('release-list')
        self.request_payload['label'] = '*' * (Release.LABEL_MAX_LENGTH + 1)

        response = self.client.post(url, self.request_payload, format='json')

        expected_error_response = {
            'label': [
                exceptions.ErrorDetail(
                    'Ensure this field has no more than 120 characters.',
                    code='max_length',
                )
            ]
        }

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data, expected_error_response)

    @responses.activate
    @mock.patch('releases.utils.tasks')
    def test_verify_release_song_data(self, mocked_tasks):
        url = reverse('release-list')

        response = self.client.post(url, self.request_payload, format='json')

        self.assertEqual(len(response.data['songs']), 2)
        self.assertEqual(response.data['songs'][0]['isrc'], self.isrc.code)
        self.assertEqual(
            response.data['songs'][1]['isrc'], self.request_payload['songs'][1]['isrc']
        )
        self.assertEqual(
            response.data['songs'][0]['youtube_content_id'],
            self.request_payload['songs'][0]['youtube_content_id'],
        )
        self.assertEqual(
            response.data['songs'][0]['cover_licensor'],
            self.request_payload['songs'][0]['cover_licensor'],
        )
        self.assertEqual(response.data['songs'][1]['cover_licensor'], '')

        song_1 = Song.objects.get(id=response.data['songs'][0]['id'])
        self.assertEqual(song_1.isrc, self.isrc)

        # Assert artists
        expected_artists_roles = self.request_payload['songs'][0][
            'artists_roles'
        ].copy()
        # The endpoint adds the users first artist as a 'primary_artist'
        # But it's filtered out in the response!
        # (ReleaseListSerializer.to_representation)
        artists_roles = response.data['songs'][0]['artists_roles']
        # Sort them both by name
        expected_artists_roles.sort(key=lambda i: i['artist_id'])
        artists_roles.sort(key=lambda i: i['artist_id'])
        for expected_artist_role, artist_role in zip(
            expected_artists_roles, artists_roles
        ):
            self.assertEqual(
                {
                    'artist_id': expected_artist_role['artist_id'],
                    'roles': expected_artist_role['roles'].sort(),
                },
                {
                    'artist_id': artist_role['artist_id'],
                    'roles': artist_role['roles'].sort(),
                },
            )

    @responses.activate
    @mock.patch('releases.utils.tasks')
    def test_song_without_filename_gets_placeholder(self, mocked_tasks):
        url = reverse('release-list')

        response = self.client.post(url, self.request_payload, format='json')

        self.assertTrue(response.data['songs'][0]['filename'])
        self.assertEqual(response.data['songs'][1]['filename'], 'N/A')

    @responses.activate
    @mock.patch('amuse.vendor.aws.transcoder.Transcoder.transcode', lambda *_: None)
    @mock.patch(
        'amuse.services.transcoding.transcode_audio_transcoder_service', lambda *_: None
    )
    def test_dropbox_audio_link(self):
        url = reverse('release-list')

        song_name = 'Tjop2'
        payload = self.request_payload
        payload["songs"] = [
            {
                **self.request_payload['songs'][0],
                'name': song_name,
                'audio_dropbox_link': 'http://some_url/song2.wav',
            }
        ]

        with mock.patch(
            'amuse.utils.download_to_bucket', self._mocked_download_to_bucket
        ):
            # Mock response for "validate_audio_url"
            responses.add(
                responses.HEAD,
                'http://some_url/song2.wav',
                content_type="audio/x-wav",
            )
            response = self.client.post(url, self.request_payload, format='json')

        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.assertEqual(len(response.data['songs']), 1)
        self.assertEqual(response.data['songs'][0]['name'], song_name)

    @responses.activate
    @mock.patch('amuse.vendor.aws.transcoder.Transcoder.transcode', lambda *_: None)
    @mock.patch(
        'amuse.services.transcoding.transcode_audio_transcoder_service', lambda *_: None
    )
    def test_google_drive_audio_file(self):
        url = reverse('release-list')

        song_name = 'Tjop3'
        payload = self.request_payload
        payload["songs"] = [
            {
                **self.request_payload['songs'][0],
                'name': song_name,
                'audio_gdrive_file_id': 'abc',
                'audio_gdrive_auth_code': '123',
            }
        ]

        with mock.patch(
            'amuse.tasks.google_drive_to_bucket.run', self._mocked_download_to_bucket
        ):
            # Mock response for "validate_audio_url"
            responses.add(
                responses.HEAD,
                'http://some_url/song2.wav',
                content_type="audio/x-wav",
            )
            response = self.client.post(url, self.request_payload, format='json')

        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.assertEqual(len(response.data['songs']), 1)
        self.assertEqual(response.data['songs'][0]['name'], song_name)

    @responses.activate
    @mock.patch('amuse.vendor.aws.transcoder.Transcoder.transcode', lambda *_: None)
    @mock.patch(
        'amuse.services.transcoding.transcode_audio_transcoder_service', lambda *_: None
    )
    def test_release_with_s3_audio_files(self):
        url = reverse('release-list')

        audio_upload_storage = S3Storage(
            bucket_name=settings.AWS_SONG_FILE_UPLOADED_BUCKET_NAME
        )
        with audio_upload_storage.open('wave.wav', 'w') as f:
            f.write(open('amuse/tests/test_api/data/wave.wav', 'rb').read())

        self.request_payload['songs'][0]['audio_s3_key'] = 'wave.wav'
        self.request_payload['songs'][1]['audio_s3_key'] = 'wave.wav'

        response = self.client.post(url, self.request_payload, format='json')

        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)

    def test_error_flags(self):
        user = UserFactory()
        artist = user.create_artist_v2('artist')
        release = ReleaseFactory(user=user)
        song = SongFactory()
        release.songs.add(song)
        SongArtistRole.objects.create(
            song=song, artist=artist, role=SongArtistRole.ROLE_PRIMARY_ARTIST
        )

        release.error_flags.artwork_text = True
        release.save()

        self.client.force_authenticate(user=user)
        url = f'/api/releases/?artist_id={artist.id}'
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        rel = next((r for r in response.data if r['id'] == release.id), None)
        self.assertTrue(rel['error_flags']['artwork_text'])
        self.assertFalse(rel['error_flags']['artwork_format'])

    def test_update(self):
        cover_art_storage = S3Storage(
            bucket_name=settings.AWS_COVER_ART_UPLOADED_BUCKET_NAME
        )
        with cover_art_storage.open('cover.jpg', 'wb') as f:
            f.write(open('amuse/tests/test_api/data/amuse.jpg', 'rb').read())

        user = UserFactory()
        artist_v2 = user.create_artist_v2('artist')
        release = ReleaseFactory(user=user)
        ReleaseArtistRole.objects.create(
            release=release,
            artist=artist_v2,
            role=ReleaseArtistRole.ROLE_PRIMARY_ARTIST,
            main_primary_artist=True,
        )
        CoverArtFactory(file='cover.jpg', release=release)

        self.client.force_authenticate(user=user)
        new_release_date = self.release_date + timedelta(days=10)
        response = self.client.patch(
            reverse('release-detail', args=[release.id]),
            data={'release_date': new_release_date.strftime('%Y-%m-%d')},
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.json())
        release.refresh_from_db()
        self.assertEqual(release.release_date, new_release_date)
        # Check that checksum was updated in the DB
        self.assertEqual(
            response.data["cover_art"]["checksum"], release.cover_art.checksum
        )

    @responses.activate
    @mock.patch('releases.utils.tasks')
    def test_release_with_original_release_date(self, mocked_tasks):
        url = reverse('release-list')
        self.request_payload['original_release_date'] = '2010-04-15'

        response = self.client.post(url, self.request_payload, format='json')

        self.assertEqual(
            self.request_payload['original_release_date'],
            response.data['original_release_date'],
        )

    @responses.activate
    @mock.patch('releases.utils.tasks')
    def test_release_with_null_original_release_date(self, mocked_tasks):
        url = reverse("release-list")
        self.request_payload["original_release_date"] = None
        response = self.client.post(url, self.request_payload, format="json")
        assert response.status_code == status.HTTP_201_CREATED

    @responses.activate
    @mock.patch('releases.utils.tasks')
    def test_song_with_original_release_date(self, mocked_tasks):
        url = reverse('release-list')

        self.request_payload['songs'][0]['original_release_date'] = '2011-08-18'
        response = self.client.post(url, self.request_payload, format='json')

        self.assertEqual(
            self.request_payload['songs'][0]['original_release_date'],
            response.data['songs'][0]['original_release_date'],
        )

    @responses.activate
    @mock.patch('releases.utils.tasks')
    def test_song_with_null_original_release_date(self, mocked_tasks):
        url = reverse("release-list")
        self.request_payload["songs"][0]["original_release_date"] = None
        response = self.client.post(url, self.request_payload, format="json")
        assert response.status_code == status.HTTP_201_CREATED

    # TODO this test should be parametrized
    @mock.patch('releases.utils.tasks')
    def test_release_mapped_status(self, mocked_tasks):
        status_mappings = [
            (Release.STATUS_SUBMITTED, ReleaseSerializer.MAPPED_PENDING_APPROVAL),
            (Release.STATUS_PENDING, ReleaseSerializer.MAPPED_PENDING_APPROVAL),
            (Release.STATUS_APPROVED, ReleaseSerializer.MAPPED_PENDING_APPROVAL),
            (Release.STATUS_UNDELIVERABLE, ReleaseSerializer.MAPPED_PENDING_APPROVAL),
            (Release.STATUS_NOT_APPROVED, ReleaseSerializer.MAPPED_NOT_APPROVED),
            (Release.STATUS_INCOMPLETE, ReleaseSerializer.MAPPED_NOT_APPROVED),
            (Release.STATUS_DELIVERED, ReleaseSerializer.MAPPED_DELIVERED),
            (Release.STATUS_RELEASED, ReleaseSerializer.MAPPED_RELEASED),
            (Release.STATUS_TAKEDOWN, ReleaseSerializer.MAPPED_TAKEDOWN),
        ]
        user = UserFactory()
        artist_v2 = user.create_artist_v2('artist')

        for input_status, expected_mapped_status in status_mappings:
            release = ReleaseFactory(user=user, status=input_status)
            ReleaseArtistRole.objects.create(
                release=release,
                artist=artist_v2,
                role=ReleaseArtistRole.ROLE_PRIMARY_ARTIST,
                main_primary_artist=True,
            )

            self.client.force_authenticate(user=user)
            response = self.client.patch(
                reverse('release-detail', args=[release.id]), format='json'
            )
            self.assertEqual(response.data['status'], expected_mapped_status)

    @responses.activate
    @mock.patch('amuse.vendor.aws.transcoder.Transcoder.transcode', lambda *_: None)
    @mock.patch(
        'amuse.services.transcoding.transcode_audio_transcoder_service', lambda *_: None
    )
    def test_elastic_transcoder_callback_when_ats_is_active(self):
        Switch.objects.create(name='service:audio-transcoder:enabled', active=True)
        url = reverse('release-list')
        response = self.client.post(url, self.request_payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        song = Song.objects.get(pk=response.data['songs'][0]['id'])
        transcoding = Transcoding.objects.create(song=song, transcoder_job=str(uuid4()))
        self.assertEqual(transcoding.status, Transcoding.STATUS_SUBMITTED)

        transcoded_storage = S3Storage(
            bucket_name=settings.AWS_SONG_FILE_TRANSCODED_BUCKET_NAME
        )
        transcoded_filename_flac = '%s.flac' % str(uuid4())
        transcoded_filename_mp3 = '%s.mp3' % str(uuid4())
        with transcoded_storage.open(transcoded_filename_flac, 'wb') as f:
            f.write(open('amuse/tests/test_api/data/flac.flac', 'rb').read())
        with transcoded_storage.open(transcoded_filename_mp3, 'wb') as f:
            f.write(open('amuse/tests/test_api/data/mp3.mp3', 'rb').read())

        self.client.post(
            '/sns/song-file-transcoder-state-change/',
            data={
                'Type': 'Notification',
                'Message': json.dumps(
                    {
                        'jobId': transcoding.transcoder_job,
                        'state': 'COMPLETED',
                        'outputs': [
                            {
                                'presetId': settings.AWS_FLAC_PRESET_ID,
                                'duration': 300,
                                'key': transcoded_filename_flac,
                            },
                            {
                                'presetId': settings.AWS_MP3128K_PRESET_ID,
                                'duration': 300,
                                'key': transcoded_filename_mp3,
                            },
                        ],
                    }
                ),
            },
            format='json',
        )

        song.refresh_from_db()
        self.assertEqual(song.files.count(), 0)

    @responses.activate
    @mock.patch('amuse.vendor.aws.transcoder.Transcoder.transcode', lambda *_: None)
    @mock.patch(
        'amuse.services.transcoding.transcode_audio_transcoder_service', lambda *_: None
    )
    def test_elastic_transcoder_callback_when_ats_is_inactive(self):
        Switch.objects.create(name='service:audio-transcoder:enabled', active=False)
        url = reverse('release-list')
        response = self.client.post(url, self.request_payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        song = Song.objects.get(pk=response.data['songs'][0]['id'])
        transcoding = Transcoding.objects.create(song=song, transcoder_job=str(uuid4()))
        self.assertEqual(transcoding.status, Transcoding.STATUS_SUBMITTED)

        transcoded_storage = S3Storage(
            bucket_name=settings.AWS_SONG_FILE_TRANSCODED_BUCKET_NAME
        )
        transcoded_filename_flac = '%s.flac' % str(uuid4())
        transcoded_filename_mp3 = '%s.mp3' % str(uuid4())
        with transcoded_storage.open(transcoded_filename_flac, 'wb') as f:
            f.write(open('amuse/tests/test_api/data/flac.flac', 'rb').read())
        with transcoded_storage.open(transcoded_filename_mp3, 'wb') as f:
            f.write(open('amuse/tests/test_api/data/mp3.mp3', 'rb').read())

        self.client.post(
            '/sns/song-file-transcoder-state-change/',
            data={
                'Type': 'Notification',
                'Message': json.dumps(
                    {
                        'jobId': transcoding.transcoder_job,
                        'state': 'COMPLETED',
                        'outputs': [
                            {
                                'presetId': settings.AWS_FLAC_PRESET_ID,
                                'duration': 300,
                                'key': transcoded_filename_flac,
                            },
                            {
                                'presetId': settings.AWS_MP3128K_PRESET_ID,
                                'duration': 300,
                                'key': transcoded_filename_mp3,
                            },
                        ],
                    }
                ),
            },
            format='json',
            **build_auth_header(settings.AWS_SNS_USER, settings.AWS_SNS_PASSWORD),
        )

        song.refresh_from_db()
        self.assertEqual(song.files.count(), 2)
        song_file_flac = song.files.get(type=SongFile.TYPE_FLAC)
        song_file_mp3 = song.files.get(type=SongFile.TYPE_MP3)
        self.assertEqual(song_file_flac.duration, 300)
        self.assertEqual(song_file_mp3.duration, 300)

    @responses.activate
    @mock.patch('amuse.vendor.aws.transcoder.Transcoder.transcode', lambda *_: None)
    @mock.patch(
        'amuse.services.transcoding.transcode_audio_transcoder_service', lambda *_: None
    )
    def test_audio_transcoder_service_callback_when_switch_is_active(self):
        Switch.objects.create(name='service:audio-transcoder:enabled', active=True)
        url = reverse('release-list')
        response = self.client.post(url, self.request_payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        song = Song.objects.get(pk=response.data['songs'][0]['id'])
        transcoding = Transcoding.objects.create(song=song, transcoder_job=str(uuid4()))
        self.assertEqual(transcoding.status, Transcoding.STATUS_SUBMITTED)

        transcoded_storage = S3Storage(
            bucket_name=settings.AWS_SONG_FILE_TRANSCODED_BUCKET_NAME
        )
        transcoded_filename_flac = '%s.flac' % str(uuid4())
        transcoded_filename_mp3 = '%s.mp3' % str(uuid4())
        with transcoded_storage.open(transcoded_filename_flac, 'wb') as f:
            f.write(open('amuse/tests/test_api/data/flac.flac', 'rb').read())
        with transcoded_storage.open(transcoded_filename_mp3, 'wb') as f:
            f.write(open('amuse/tests/test_api/data/mp3.mp3', 'rb').read())

        self.client.post(
            '/sns/notification/',
            json.dumps(
                {
                    'Type': 'Notification',
                    'TopicArn': settings.AUDIO_TRANSCODER_SERVICE_RESPONSE_TOPIC,
                    'Message': json.dumps(
                        {
                            'id': transcoding.id,
                            'status': 'success',
                            'errors': None,
                            'outputs': [
                                {
                                    'format': 'flac',
                                    'duration': 300,
                                    'key': transcoded_filename_flac,
                                    'bucket': str(uuid4()),
                                },
                                {
                                    'format': 'mp3',
                                    'duration': 300,
                                    'key': transcoded_filename_mp3,
                                    'bucket': str(uuid4()),
                                },
                            ],
                        }
                    ),
                }
            ),
            content_type='application/json',
            **build_auth_header(settings.AWS_SNS_USER, settings.AWS_SNS_PASSWORD),
        )

        song.refresh_from_db()
        self.assertEqual(song.files.count(), 2)
        song_file_flac = song.files.get(type=SongFile.TYPE_FLAC)
        song_file_mp3 = song.files.get(type=SongFile.TYPE_MP3)
        self.assertEqual(song_file_flac.duration, 300)
        self.assertEqual(song_file_mp3.duration, 300)

    @responses.activate
    @mock.patch('amuse.vendor.aws.transcoder.Transcoder.transcode', lambda *_: None)
    @mock.patch(
        'amuse.services.transcoding.transcode_audio_transcoder_service', lambda *_: None
    )
    def test_audio_transcoder_service_callback_when_switch_is_inactive(self):
        Switch.objects.create(name='service:audio-transcoder:enabled', active=False)
        url = reverse('release-list')
        response = self.client.post(url, self.request_payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        song = Song.objects.get(pk=response.data['songs'][0]['id'])
        transcoding = Transcoding.objects.create(song=song, transcoder_job=str(uuid4()))
        self.assertEqual(transcoding.status, Transcoding.STATUS_SUBMITTED)

        transcoded_storage = S3Storage(
            bucket_name=settings.AWS_SONG_FILE_TRANSCODED_BUCKET_NAME
        )
        transcoded_filename_flac = '%s.flac' % str(uuid4())
        transcoded_filename_mp3 = '%s.mp3' % str(uuid4())
        with transcoded_storage.open(transcoded_filename_flac, 'wb') as f:
            f.write(open('amuse/tests/test_api/data/flac.flac', 'rb').read())
        with transcoded_storage.open(transcoded_filename_mp3, 'wb') as f:
            f.write(open('amuse/tests/test_api/data/mp3.mp3', 'rb').read())

        self.client.post(
            '/sns/notification/',
            data={
                'Type': 'Notification',
                'TopicArn': settings.AUDIO_TRANSCODER_SERVICE_RESPONSE_TOPIC,
                'Message': json.dumps(
                    {
                        'id': transcoding.id,
                        'status': 'success',
                        'errors': None,
                        'outputs': [
                            {
                                'format': 'flac',
                                'duration': 300,
                                'key': transcoded_filename_flac,
                                'bucket': str(uuid4()),
                            },
                            {
                                'format': 'mp3',
                                'duration': 300,
                                'key': transcoded_filename_mp3,
                                'bucket': str(uuid4()),
                            },
                        ],
                    }
                ),
            },
            format='json',
            **build_auth_header(settings.AWS_SNS_USER, settings.AWS_SNS_PASSWORD),
        )

        song.refresh_from_db()
        self.assertEqual(song.files.count(), 0)

    @responses.activate
    @mock.patch('releases.utils.tasks')
    def test_release_with_language_sets_the_language(self, mocked_tasks):
        url = reverse('release-list')

        lang = MetadataLanguageFactory()
        self.request_payload['language_code'] = lang.fuga_code

        response = self.client.post(url, self.request_payload, format='json')

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        meta_language_not_in_response_data = response.data.get('language_code') is None
        self.assertTrue(meta_language_not_in_response_data)

        release = Release.objects.get(pk=response.data['id'])

        self.assertEqual(release.meta_language.id, lang.id)

        self.assertEqual(release.meta_language.name, lang.name)

    @responses.activate
    @mock.patch('releases.utils.tasks')
    def test_release_without_language_is_valid(self, mocked_tasks):
        url = reverse('release-list')

        self.request_payload.pop('language_code', None)

        response = self.client.post(url, self.request_payload, format='json')

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertFalse(response.data.get('language_code'))

    @responses.activate
    @mock.patch('releases.utils.tasks')
    def test_release_with_empty_language_is_valid(self, mocked_tasks):
        url = reverse('release-list')

        self.request_payload['language_code'] = None

        response = self.client.post(url, self.request_payload, format='json')

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    @responses.activate
    def test_release_with_invalid_language_returns_validation_error(self):
        url = reverse('release-list')

        self.request_payload['language_code'] = -1

        response = self.client.post(url, self.request_payload, format='json')

        expected_error_response = {
            'language_code': [
                exceptions.ErrorDetail('Invalid language', code='invalid')
            ]
        }

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data, expected_error_response)

    @responses.activate
    @mock.patch('releases.utils.tasks')
    def test_release_with_duplicate_ISRC_returns_validation_error(self, mocked_tasks):
        url = reverse('release-list')

        self.request_payload['songs'][0]['isrc'] = 'TEST12345678'
        self.request_payload['songs'][1]['isrc'] = 'TEST12345678'

        response = self.client.post(url, self.request_payload, format='json')

        expected_error_response = {
            'songs': [exceptions.ErrorDetail('Duplicate ISRC', code='invalid')]
        }

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data, expected_error_response)

    @responses.activate
    @mock.patch('releases.utils.tasks')
    def test_song_with_language_sets_the_language(self, mocked_tasks):
        url = reverse('release-list')

        lang = MetadataLanguageFactory()

        self.request_payload['songs'].pop(0)
        self.request_payload['songs'][0]['language_code'] = lang.fuga_code

        response = self.client.post(url, self.request_payload, format='json')

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        language_response_data = response.data['songs'][0].get('language_code')
        self.assertIsNone(language_response_data)

        release = Release.objects.get(pk=response.data['id'])
        songs = release.songs.all()

        self.assertEqual(songs[0].meta_language.id, lang.id)
        self.assertEqual(songs[0].meta_language.name, lang.name)

    @responses.activate
    @mock.patch('releases.utils.tasks')
    def test_song_without_language_is_valid(self, mocked_tasks):
        url = reverse('release-list')

        self.request_payload['songs'].pop(0)
        self.request_payload['songs'][0].pop('language_code', None)

        response = self.client.post(url, self.request_payload, format='json')

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertFalse(response.data.get('language_code'))

    @responses.activate
    @mock.patch('releases.utils.tasks')
    def test_song_with_empty_language_is_valid(self, mocked_tasks):
        url = reverse('release-list')

        self.request_payload['songs'].pop(0)
        self.request_payload['songs'][0]['language_code'] = None

        response = self.client.post(url, self.request_payload, format='json')

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    @responses.activate
    def test_song_with_invalid_language_returns_validation_error(self):
        url = reverse('release-list')

        self.request_payload['songs'].pop(0)
        self.request_payload['songs'][0]['language_code'] = 'invalid'

        response = self.client.post(url, self.request_payload, format='json')

        expected_error_response = {
            'songs': [
                {
                    'language_code': [
                        exceptions.ErrorDetail('Invalid language', code='invalid')
                    ]
                }
            ]
        }

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data, expected_error_response)

    @responses.activate
    @mock.patch('releases.utils.tasks')
    def test_song_with_audio_language_sets_the_audio_locale(self, mocked_tasks):
        url = reverse('release-list')

        lang = MetadataLanguageFactory()

        self.request_payload['songs'].pop(0)
        self.request_payload['songs'][0]['audio_language_code'] = lang.fuga_code

        response = self.client.post(url, self.request_payload, format='json')

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        language_response_data = response.data['songs'][0].get('audio_language_code')
        self.assertIsNone(language_response_data)

        release = Release.objects.get(pk=response.data['id'])
        songs = release.songs.all()

        self.assertEqual(songs[0].meta_audio_locale.id, lang.id)
        self.assertEqual(songs[0].meta_audio_locale.name, lang.name)

    @responses.activate
    @mock.patch('releases.utils.tasks')
    def test_song_without_audio_language_is_valid(self, mocked_tasks):
        url = reverse('release-list')

        self.request_payload['songs'].pop(0)
        self.request_payload['songs'][0].pop('audio_language_code', None)

        response = self.client.post(url, self.request_payload, format='json')

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertFalse(response.data.get('audio_language_code'))

    @responses.activate
    @mock.patch('releases.utils.tasks')
    def test_song_with_empty_audio_language_is_valid(self, mocked_tasks):
        url = reverse('release-list')

        self.request_payload['songs'].pop(0)
        self.request_payload['songs'][0]['audio_language_code'] = None

        response = self.client.post(url, self.request_payload, format='json')

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    @responses.activate
    def test_song_with_invalid_audio_language_returns_validation_error(self):
        url = reverse('release-list')

        self.request_payload['songs'].pop(0)
        self.request_payload['songs'][0]['audio_language_code'] = 'invalid'

        response = self.client.post(url, self.request_payload, format='json')

        expected_error_response = {
            'songs': [
                {
                    'audio_language_code': [
                        exceptions.ErrorDetail('Invalid language', code='invalid')
                    ]
                }
            ]
        }

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data, expected_error_response)

    @responses.activate
    @mock.patch('releases.utils.tasks')
    def test_song_with_genre_not_qualified_for_yt_content_id(self, mocked_tasks):
        url = reverse('release-list')

        request_payload = self.request_payload
        request_payload['songs'].pop(0)
        request_payload['songs'].append(copy.deepcopy(request_payload['songs'][0]))
        request_payload['songs'].append(copy.deepcopy(request_payload['songs'][0]))

        for i, name in enumerate(['Electronic', 'Hip Hop/Rap', 'New Age']):
            genre = GenreFactory(name=name)
            request_payload['songs'][i]['genre'] = {'id': genre.id, 'name': genre.name}
            request_payload['songs'][i]['sequence'] = i
            request_payload['songs'][i]['youtube_content_id'] = 'monetize'
            request_payload['songs'][i]['isrc'] = f'UNIQ1234876{i}'

        response = self.client.post(url, request_payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        release = Release.objects.get(pk=response.data['id'])
        songs = release.songs.filter(youtube_content_id=Song.YT_CONTENT_ID_NONE)

        self.assertEqual(songs.count(), 3)
        self.assertIn(
            Store.get_yt_content_id_store().id, list(release.excluded_store_ids)
        )

    @responses.activate
    @mock.patch('releases.utils.tasks')
    def test_song_with_child_genre_not_qualified_for_yt_content_id(self, mocked_tasks):
        url = reverse('release-list')

        genre = GenreFactory(name='Electronic')
        child_genre = GenreFactory(parent=genre)
        request_payload = copy.deepcopy(self.request_payload)
        request_payload['songs'][0]['genre'] = {
            'id': child_genre.id,
            'name': child_genre.name,
        }
        request_payload['songs'][0]['youtube_content_id'] = 'none'

        response = self.client.post(url, request_payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        release = Release.objects.get(pk=response.data['id'])
        song = release.songs.all()[0]

        self.assertEqual(song.youtube_content_id, Song.YT_CONTENT_ID_NONE)
        self.assertIn(
            Store.get_yt_content_id_store().id, list(release.excluded_store_ids)
        )

    @responses.activate
    @mock.patch('releases.utils.tasks')
    def test_free_user_release_has_27_days_limit(self, mocked_tasks):
        Subscription.objects.filter(user=self.user).delete()
        for song in self.request_payload['songs']:
            song['royalty_splits'] = [{'user_id': self.user.id, 'rate': 1}]

        url = reverse('release-list')
        self.release_date = timezone.now().date() + timedelta(days=26)
        self.request_payload['release_date'] = self.release_date.strftime('%Y-%m-%d')
        response = self.client.post(url, self.request_payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        self.release_date = timezone.now().date() + timedelta(days=27)
        self.request_payload['release_date'] = self.release_date.strftime('%Y-%m-%d')
        response = self.client.post(url, self.request_payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    @responses.activate
    @mock.patch('releases.utils.tasks')
    def test_always_qualify_for_yt_content_id_for_priority_user(self, mocked_tasks):
        url = reverse('release-list')

        genre = GenreFactory(name='Electronic')
        request_payload = copy.deepcopy(self.request_payload)
        request_payload['songs'][0]['genre'] = {'id': genre.id, 'name': genre.name}
        request_payload['songs'][0]['youtube_content_id'] = 'monetize'
        self.user.category = User.CATEGORY_PRIORITY
        self.user.save()

        response = self.client.post(url, request_payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        release = Release.objects.get(pk=response.data['id'])
        song = release.songs.all()[0]

        self.assertEqual(song.youtube_content_id, Song.YT_CONTENT_ID_MONETIZE)
        self.assertNotIn(
            Store.get_yt_content_id_store().id, list(release.excluded_store_ids)
        )

    @responses.activate
    @mock.patch('releases.utils.tasks')
    def test_create_release_with_minimal_payload(self, mocked_tasks):
        url = reverse('release-list')

        genre = GenreFactory()

        request_payload = {
            'name': 'Postman Release (v4)',
            'cover_art_filename': 'cover.jpg',
            'release_date': self.release_date.strftime('%Y-%m-%d'),
            'excluded_stores': [],
            'excluded_countries': [],
            'artist_id': self.artist_1.id,
            'songs': [
                {
                    'name': 'Test Song 2',
                    'sequence': 1,
                    'explicit': 'none',
                    'recording_year': '1900',
                    'origin': 'cover',
                    'youtube_content_id': 'none',
                    'cover_licensor': '',
                    'filename': 'users_filename.wav',
                    'genre': {'id': self.genre.id, 'name': 'Genre'},
                    'artists_roles': [
                        {'roles': ['primary_artist'], 'artist_id': self.artist_1.id},
                        {'roles': ['producer'], 'artist_id': self.artist_4.id},
                    ],
                    'royalty_splits': [
                        {'user_id': self.user.id, 'rate': 0.75},
                        {'user_id': self.user_4.id, 'rate': 0.25},
                    ],
                }
            ],
        }

        response = self.client.post(url, request_payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.json())
        release = Release.objects.get(id=response.data['id'])
        song_1 = Song.objects.get(id=response.data['songs'][0]['id'])

        # Test newly created release does not have upc
        self.assertIsNone(release.upc)

        # Assert correct ReleseArtistRole value is created
        artist_v2_1 = self.user.artists.get(id=self.artist_1.id)

        self.assertEqual(
            artist_v2_1, ReleaseArtistRole.objects.get(release=release).artist
        )

        # Assert SongArtisRole is created

        song_1_artist_role = SongArtistRole.objects.get(
            song=song_1, role=SongArtistRole.ROLE_PRIMARY_ARTIST
        )
        self.assertEqual(song_1_artist_role.artist, artist_v2_1)

        self.assertEqual(release.release_date, self.release_date)
        # Default to static release if not given
        self.assertEqual(
            Release.SCHEDULE_TYPES_MAP[Release.SCHEDULE_TYPE_STATIC],
            response.data['schedule_type'],
        )

        # Assert asset labels are created
        assert release.asset_labels.all().count() > 0
        assert song_1.asset_labels.all().count() > 0

    @responses.activate
    @mock.patch('releases.utils.tasks')
    def test_create_asap_release_no_release_date(self, mocked_tasks):
        url = reverse('release-list')
        self.request_payload['schedule_type'] = Release.SCHEDULE_TYPES_MAP[
            Release.SCHEDULE_TYPE_ASAP
        ]
        self.request_payload.pop('release_date')
        response = self.client.post(url, self.request_payload, format='json')
        self.assertEqual(
            Release.SCHEDULE_TYPES_MAP[Release.SCHEDULE_TYPE_ASAP],
            response.data['schedule_type'],
        )
        assert (
            datetime.strptime(response.data['created'], '%Y-%m-%dT%H:%M:%S.%fZ').date()
            == datetime.strptime(response.data['release_date'], '%Y-%m-%d').date()
        )
        release = Release.objects.get(id=response.data['id'])
        self.assertIsNone(release.release_date)
        self.assertEqual(release.schedule_type, Release.SCHEDULE_TYPE_ASAP)

    @responses.activate
    @mock.patch('releases.utils.tasks')
    def test_create_asap_release_none_release_date(self, mocked_tasks):
        url = reverse('release-list')
        self.request_payload['schedule_type'] = Release.SCHEDULE_TYPES_MAP[
            Release.SCHEDULE_TYPE_ASAP
        ]
        self.request_payload['release_date'] = None
        response = self.client.post(url, self.request_payload, format='json')
        self.assertEqual(
            Release.SCHEDULE_TYPES_MAP[Release.SCHEDULE_TYPE_ASAP],
            response.data['schedule_type'],
        )
        assert (
            datetime.strptime(response.data['created'], '%Y-%m-%dT%H:%M:%S.%fZ').date()
            == datetime.strptime(response.data['release_date'], '%Y-%m-%d').date()
        )
        release = Release.objects.get(id=response.data['id'])
        self.assertIsNone(release.release_date)
        self.assertEqual(release.schedule_type, Release.SCHEDULE_TYPE_ASAP)

    @responses.activate
    @mock.patch('releases.utils.tasks')
    def test_create_asap_release_with_release_date(self, mocked_tasks):
        url = reverse('release-list')
        self.request_payload['schedule_type'] = Release.SCHEDULE_TYPES_MAP[
            Release.SCHEDULE_TYPE_ASAP
        ]
        response = self.client.post(url, self.request_payload, format='json')
        self.assertEqual(
            Release.SCHEDULE_TYPES_MAP[Release.SCHEDULE_TYPE_ASAP],
            response.data['schedule_type'],
        )
        assert (
            datetime.strptime(response.data['created'], '%Y-%m-%dT%H:%M:%S.%fZ').date()
            == datetime.strptime(response.data['release_date'], '%Y-%m-%d').date()
        )
        release = Release.objects.get(id=response.data['id'])
        self.assertIsNone(release.release_date)
        self.assertEqual(release.schedule_type, Release.SCHEDULE_TYPE_ASAP)

    @responses.activate
    @mock.patch('releases.utils.tasks')
    def test_create_release_no_schedule_type_and_release_date(self, mocked_tasks):
        url = reverse('release-list')
        self.request_payload.pop('schedule_type')
        self.request_payload.pop('release_date')
        expected_error_message = 'Release date is required for static releases '
        response = self.client.post(url, self.request_payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        error = response.data['non_field_errors'][0]
        self.assertEqual(error, expected_error_message)

    @responses.activate
    def test_fetching_releases_for_artist(self):
        release1 = ReleaseFactory()
        song1 = SongFactory()
        release1.songs.add(song1)
        release2 = ReleaseFactory()
        song2 = SongFactory()
        release2.songs.add(song2)
        release3 = ReleaseFactory()
        SongArtistRole.objects.create(
            song=song1, artist=self.artist_1, role=SongArtistRole.ROLE_PRIMARY_ARTIST
        )
        SongArtistRole.objects.create(
            song=song2, artist=self.artist_1, role=SongArtistRole.ROLE_PRIMARY_ARTIST
        )

        url = f'/api/releases/?artist_id={self.artist_1.id}'
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertEqual(len(response.data), 2)

    @responses.activate
    def test_fetching_asap_and_static_releases(self):
        created = timezone.now().date()
        release_date = created + timedelta(days=10)
        release1 = ReleaseFactory(
            release_date=None,
            created=created,
            schedule_type=Release.SCHEDULE_TYPE_ASAP,
            status=Release.STATUS_PENDING,
        )
        release2 = ReleaseFactory(
            release_date=release_date,
            created=created,
            schedule_type=Release.SCHEDULE_TYPE_STATIC,
        )
        song1 = SongFactory()
        song2 = SongFactory()
        song3 = SongFactory()
        release1.songs.add(song1)
        release2.songs.add(song2)
        release2.songs.add(song3)

        SongArtistRole.objects.create(
            song=song1, artist=self.artist_1, role=SongArtistRole.ROLE_PRIMARY_ARTIST
        )
        SongArtistRole.objects.create(
            song=song2, artist=self.artist_1, role=SongArtistRole.ROLE_PRIMARY_ARTIST
        )
        SongArtistRole.objects.create(
            song=song3, artist=self.artist_1, role=SongArtistRole.ROLE_PRIMARY_ARTIST
        )

        url = reverse('release-list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertEqual(len(response.data), 2)
        self.assertEqual(
            response.data[0]['schedule_type'],
            Release.SCHEDULE_TYPES_MAP[Release.SCHEDULE_TYPE_ASAP],
        )
        self.assertEqual(response.data[0]['release_date'], str(created))
        self.assertEqual(
            response.data[1]['schedule_type'],
            Release.SCHEDULE_TYPES_MAP[Release.SCHEDULE_TYPE_STATIC],
        )
        self.assertEqual(response.data[1]['release_date'], str(release_date))
        release1.refresh_from_db()
        release2.refresh_from_db()
        self.assertIsNone(release1.release_date)
        self.assertEqual(release2.release_date, release_date)

    @skip
    @responses.activate
    def test_member_cant_delete_release(self):
        artist = Artistv2Factory()
        UserArtistRole.objects.create(
            user=self.user, artist=artist, type=UserArtistRole.MEMBER
        )
        release = ReleaseFactory()
        ReleaseArtistRole.objects.create(
            release=release,
            artist=artist,
            role=ReleaseArtistRole.ROLE_PRIMARY_ARTIST,
            main_primary_artist=True,
        )
        url = f'/api/releases/{release.id}/'
        response = self.client.delete(url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    @skip
    @responses.activate
    def test_admin_can_delete_release(self):
        artist = Artistv2Factory()
        UserArtistRole.objects.create(
            user=self.user, artist=artist, type=UserArtistRole.ADMIN
        )
        release = ReleaseFactory()
        ReleaseArtistRole.objects.create(
            release=release,
            artist=artist,
            role=ReleaseArtistRole.ROLE_PRIMARY_ARTIST,
            main_primary_artist=True,
        )
        url = f'/api/releases/{release.id}/'
        response = self.client.delete(url)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

    @responses.activate
    def test_deleted_rejected_releases_are_hidden(self):
        release1 = ReleaseFactory()
        song1 = SongFactory()
        release1.songs.add(song1)
        release2 = ReleaseFactory(status=Release.STATUS_DELETED)
        song2 = SongFactory()
        release2.songs.add(song2)
        release3 = ReleaseFactory(status=Release.STATUS_REJECTED)
        song3 = SongFactory()
        release3.songs.add(song3)
        SongArtistRole.objects.create(
            song=song1, artist=self.artist_1, role=SongArtistRole.ROLE_PRIMARY_ARTIST
        )
        SongArtistRole.objects.create(
            song=song2, artist=self.artist_1, role=SongArtistRole.ROLE_PRIMARY_ARTIST
        )
        SongArtistRole.objects.create(
            song=song3, artist=self.artist_1, role=SongArtistRole.ROLE_PRIMARY_ARTIST
        )

        url = f'/api/releases/?artist_id={self.artist_1.id}'
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertEqual(len(response.data), 1)

    @responses.activate
    def test_fetching_contributing_releases_for_artist(self):
        release = ReleaseFactory()
        song = SongFactory(release=release)
        release.songs.add(song)
        SongArtistRole.objects.create(
            song=song, artist=self.artist_1, role=SongArtistRole.ROLE_WRITER
        )

        url = f'/api/releases/?artist_id={self.artist_1.id}'
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertEqual(len(response.data), 1, response.data)
        fetched_release = response.data[0]
        self.assertEqual(fetched_release['id'], release.id, release)

    @responses.activate
    def test_fetching_not_allowed_for_foreign_artists(self):
        release1 = ReleaseFactory()
        song1 = SongFactory()
        release1.songs.add(song1)
        SongArtistRole.objects.create(
            song=song1, artist=self.artist_2, role=SongArtistRole.ROLE_PRIMARY_ARTIST
        )

        url = f'/api/releases/?artist_id={self.artist_2.id}'
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertEqual(response.data, [])

        self.client.force_authenticate(user=self.user_2)

        url = f'/api/releases/?artist_id={self.artist_2.id}'
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['id'], release1.id)

    @responses.activate
    def test_fetching_roles_with_release(self):
        release = ReleaseFactory()
        song = SongFactory(release=release)
        release.songs.add(song)
        ReleaseArtistRole.objects.create(
            release=release,
            artist=self.artist_1,
            role=ReleaseArtistRole.ROLE_PRIMARY_ARTIST,
        )
        SongArtistRole.objects.create(
            song=song, artist=self.artist_1, role=SongArtistRole.ROLE_WRITER
        )

        url = f'/api/releases/?artist_id={self.artist_1.id}'
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        roles = response.data[0]['artist_roles']

        self.assertEqual(len(roles), 1)
        self.assertEqual(roles[0]['artist_id'], self.artist_1.id)
        self.assertEqual(roles[0]['role'], 'primary_artist')
        self.assertEqual(roles[0]['artist_name'], self.artist_1.name)

    @responses.activate
    @mock.patch('releases.utils.tasks')
    def test_release_artist_role_populated(self, mocked_tasks):
        url = reverse('release-list')
        response = self.client.post(url, self.request_payload, format='json')
        primary_artist = self.user.artists.first()
        release = Release.objects.get(id=response.data['id'])
        # Assert primary artist added
        self.assertEqual(
            primary_artist,
            ReleaseArtistRole.objects.get(
                release=release, role=ReleaseArtistRole.ROLE_PRIMARY_ARTIST
            ).artist,
        )

    @responses.activate
    @mock.patch('releases.utils.tasks')
    def test_release_return_400_when_artist_id_is_missing_in_artists_roles(
        self, mocked_tasks
    ):
        url = reverse('release-list')
        self.request_payload['songs'][0]['artists_roles'] = [{'roles': ['producer']}]
        response = self.client.post(url, self.request_payload, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(
            response.data['songs'][0]['artists_roles'][0]['artist_id'][0],
            exceptions.ErrorDetail('This field is required.', code='required'),
        )

    @responses.activate
    @mock.patch('releases.utils.tasks')
    def test_release_return_400_when_roles_are_missing_in_artists_roles(
        self, mocked_tasks
    ):
        url = reverse('release-list')
        self.request_payload['songs'][0]['artists_roles'] = [
            {'artist_id': self.artist_1.id}
        ]
        response = self.client.post(url, self.request_payload, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(
            response.data['songs'][0]['artists_roles'][0]['roles'][0],
            exceptions.ErrorDetail('This field is required.', code='required'),
        )

    @responses.activate
    @mock.patch('releases.utils.tasks')
    def test_release_return_400_artists_roles_is_empty(self, mocked_tasks):
        url = reverse('release-list')
        self.request_payload['songs'][0]['artists_roles'] = []
        response = self.client.post(url, self.request_payload, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(
            response.data['songs'][0]['artists_roles'][0],
            exceptions.ErrorDetail("Artists' roles are required.", code='invalid'),
        )

    @responses.activate
    @mock.patch('releases.utils.tasks')
    def test_release_return_400_artists_roles_is_has_invalid_role(self, mocked_tasks):
        url = reverse('release-list')
        self.request_payload['songs'][0]['artists_roles'] = [
            {'artist_id': self.artist_1.id, 'roles': ['invalid_role']}
        ]
        response = self.client.post(url, self.request_payload, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        self.assertEqual(
            response.data['songs'][0]['artists_roles'][0]['roles'][0],
            exceptions.ErrorDetail('Invalid value for role', code='invalid'),
        )

    @responses.activate
    @mock.patch('releases.utils.tasks')
    def test_song_artist_role_populated(self, mocked_tasks):
        url = reverse('release-list')
        response = self.client.post(url, self.request_payload, format='json')
        song_1 = Song.objects.get(id=response.data['songs'][0]['id'])
        primary_artist = self.user.artists.first()
        featured_artist = ArtistV2.objects.get(name='FeaturedArtist')
        writer_artist = ArtistV2.objects.get(name='Writer Artist')
        producer_artist = ArtistV2.objects.get(name='ProducerdArtist')

        # Assert primary artist added to song
        song_1_artist_role_primary = SongArtistRole.objects.get(
            song=song_1, role=SongArtistRole.ROLE_PRIMARY_ARTIST
        )
        self.assertEqual(song_1_artist_role_primary.artist, primary_artist)

        # Assert rest of roles correctly added to SongArtistRole
        song_1_artist_role_featured = SongArtistRole.objects.get(
            song=song_1, role=SongArtistRole.ROLE_FEATURED_ARTIST
        )
        self.assertEqual(song_1_artist_role_featured.artist, featured_artist)

        song_1_artist_role_writer = SongArtistRole.objects.get(
            song=song_1, role=SongArtistRole.ROLE_WRITER
        )
        self.assertEqual(song_1_artist_role_writer.artist, writer_artist)

        song_1_artist_role_producer = SongArtistRole.objects.get(
            song=song_1, role=SongArtistRole.ROLE_PRODUCER
        )
        self.assertEqual(song_1_artist_role_producer.artist, producer_artist)

    @responses.activate
    def test_release_genre_set_from_dominant_genre(self):
        url = reverse('release-list')

        genres = [GenreFactory(), GenreFactory()]

        self.request_payload['songs'] = [
            {
                'name': 'Tjop',
                'filename': 'song.wav',
                'sequence': 0,
                'version': '1',
                'explicit': 'explicit',
                'recording_year': '2018',
                'origin': 'original',
                'youtube_content_id': 'block',
                'cover_licensor': 'foobar',
                'isrc': 'AA0001234567',
                'genre': {'id': genres[0].id, 'name': genres[0].name},
                'artists_roles': [
                    {'roles': ['primary_artist'], 'artist_id': self.artist_1.id},
                    {'roles': ['producer'], 'artist_id': self.artist_4.id},
                ],
                'royalty_splits': [
                    {'user_id': self.user.id, 'rate': 0.6},
                    {'user_id': self.user_4.id, 'rate': 0.4},
                ],
            },
            {
                'name': 'Test Song 2',
                'filename': '',
                'sequence': 1,
                'version': '',
                'cover_licensor': '',
                'explicit': 'none',
                'recording_year': '1900',
                'origin': 'cover',
                'youtube_content_id': 'none',
                'isrc': 'TEST12345678',
                'genre': {'id': genres[1].id, 'name': genres[1].name},
                'artists_roles': [
                    {'roles': ['primary_artist'], 'artist_id': self.artist_1.id},
                    {'roles': ['producer'], 'artist_id': self.artist_4.id},
                ],
                'royalty_splits': [
                    {'user_id': self.user.id, 'rate': 0.5},
                    {'user_id': self.user_4.id, 'rate': 0.5},
                ],
            },
            {
                'name': 'Test Song 3',
                'filename': '',
                'sequence': 1,
                'version': '',
                'cover_licensor': '',
                'explicit': 'none',
                'recording_year': '1900',
                'origin': 'cover',
                'youtube_content_id': 'none',
                'isrc': 'TEST12348765',
                'genre': {'id': genres[1].id, 'name': genres[1].name},
                'artists_roles': [
                    {'roles': ['primary_artist'], 'artist_id': self.artist_1.id},
                    {'roles': ['producer'], 'artist_id': self.artist_4.id},
                ],
                'royalty_splits': [
                    {'user_id': self.user.id, 'rate': 0.75},
                    {'user_id': self.user_4.id, 'rate': 0.25},
                ],
            },
        ]
        self.client.force_authenticate(user=self.user)
        response = self.client.post(url, self.request_payload, format='json')

        release = Release.objects.get(pk=response.data['id'])

        self.assertEqual(release.genre.id, genres[1].id)

    @responses.activate
    @mock.patch('releases.utils.tasks')
    def test_create_event_is_created_with_release(self, mocked_tasks):
        url = reverse('release-list')
        response = self.client.post(
            url,
            self.request_payload,
            format='json',
            headers={'User-Agent': 'amuse-web/1.2.3;'},
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        release = Release.objects.get(pk=response.data['id'])
        self.assertEqual(
            Event.objects.content_object(release).type(Event.TYPE_CREATE).count(), 1
        )

    @responses.activate
    @mock.patch('releases.utils.tasks')
    def test_release_royalty_splits_rates_total_not_equal_to_one(self, mocked_tasks):
        url = reverse('release-list')
        self.request_payload['songs'][0]['royalty_splits'][0]['rate'] = 0.1

        response = self.client.post(url, self.request_payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        expected_error_message = (
            "The sum of the royalty splits' rates is not equal to 1"
        )
        returned_error_message = response.json()['songs'][0]['royalty_splits'][0]

        self.assertEqual(returned_error_message, expected_error_message)

    @responses.activate
    @mock.patch('releases.utils.tasks')
    def test_release_royalty_splits_(self, mocked_tasks):
        url = reverse('release-list')
        invite = {
            'name': 'New Artist',
            'email': 'artist@example.com',
            'phone_number': '+46723712345',
        }

        rate_1 = 0.75
        rate_2 = 0.25

        royalty_splits = [
            {'user_id': self.user_4.id, 'rate': rate_1},
            {'user_id': self.user_3.id, 'rate': rate_2, 'invite': invite},
        ]
        self.request_payload['songs'][0]['royalty_splits'] = royalty_splits

        self.assertEqual(
            0, RoyaltySplit.objects.filter(status=RoyaltySplit.STATUS_PENDING).count()
        )

        response = self.client.post(url, self.request_payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        self.assertEqual(
            3, RoyaltySplit.objects.filter(status=RoyaltySplit.STATUS_PENDING).count()
        )
        self.assertEqual(
            1, RoyaltySplit.objects.filter(status=RoyaltySplit.STATUS_CONFIRMED).count()
        )

    @responses.activate
    @mock.patch('releases.utils.tasks')
    def test_song_artist_invite_created(self, mocked_tasks):
        url = reverse('release-list')
        invite_artist = Artistv2Factory(name='InviteMe')
        invite_artist2 = Artistv2Factory(name='InviteMe2')
        self.request_payload['songs'][0]['artists_invites'] = [
            {'email': 'test@example.com', 'artist_id': invite_artist.id}
        ]
        self.request_payload['songs'][1]['artists_invites'] = [
            {'email': 'test2@example.com', 'artist_id': invite_artist2.id},
            {'email': 'test@example.com', 'artist_id': invite_artist.id},
        ]
        response = self.client.post(url, self.request_payload, format='json')
        release = Release.objects.get(id=response.data['id'])
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        song_1 = Song.objects.get(id=response.data['songs'][0]['id'])
        song_2 = Song.objects.get(id=response.data['songs'][1]['id'])
        invites = SongArtistInvitation.objects.filter(
            status=SongArtistInvitation.STATUS_CREATED, song__release=release.id
        ).distinct('email', 'phone_number')
        song_invite = SongArtistInvitation.objects.filter(song=song_1).first()
        song_invite2 = SongArtistInvitation.objects.filter(song=song_2).first()
        self.assertEqual(len(invites), 2)
        self.assertEqual(song_invite.status, SongArtistInvitation.STATUS_CREATED)
        self.assertEqual(song_invite.song, song_1)
        self.assertEqual(song_invite.artist, invite_artist)
        self.assertEqual(song_invite2.status, SongArtistInvitation.STATUS_CREATED)
        self.assertEqual(song_invite2.song, song_2)
        self.assertEqual(song_invite2.artist, invite_artist2)

    def _mocked_download_to_bucket(self, *args, **kwargs):
        audio_upload_storage = S3Storage(
            bucket_name=settings.AWS_SONG_FILE_UPLOADED_BUCKET_NAME
        )
        with self._file() as (_, f):
            with audio_upload_storage.open('wave2.wav', 'w') as f2:
                f2.write(f.read())

    @responses.activate
    @mock.patch('releases.utils.tasks')
    def test_artist_sequence_sar_rar(self, mocked_tasks):
        url = reverse('release-list')
        response = self.client.post(url, self.request_payload, format='json')

        song_1 = Song.objects.get(id=response.data['songs'][0]['id'])
        song_2 = Song.objects.get(id=response.data['songs'][1]['id'])

        sar_1_primary = SongArtistRole.objects.get(
            song=song_1, artist=self.artist_1, role=SongArtistRole.ROLE_PRIMARY_ARTIST
        )
        self.assertEqual(sar_1_primary.artist_sequence, 1)

        sar_1_featured = SongArtistRole.objects.get(
            song=song_1, artist=self.artist_2, role=SongArtistRole.ROLE_FEATURED_ARTIST
        )

        self.assertEqual(sar_1_featured.artist_sequence, 2)

        sar_2_primary = SongArtistRole.objects.get(
            song=song_2, artist=self.artist_1, role=SongArtistRole.ROLE_PRIMARY_ARTIST
        )

        self.assertEqual(sar_2_primary.artist_sequence, 1)

        sar_2_producer = SongArtistRole.objects.get(
            song=song_2, artist=self.artist_4, role=SongArtistRole.ROLE_PRODUCER
        )

        self.assertEqual(sar_2_producer.artist_sequence, 2)

    @responses.activate
    @mock.patch('releases.utils.tasks')
    def test_creation_user_should_equal_artist_owner(self, mocked_tasks):
        artist = Artistv2Factory()
        UserArtistRole.objects.create(
            artist=artist, user=self.user, type=UserArtistRole.ADMIN
        )
        self.request_payload['artist_id'] = artist.id
        self.request_payload['songs'][0]['artists_roles'].append(
            {'artist_id': artist.id, 'roles': ['primary_artist']}
        )
        self.request_payload['songs'][1]['artists_roles'].append(
            {'artist_id': artist.id, 'roles': ['primary_artist']}
        )

        url = reverse('release-list')
        response = self.client.post(url, self.request_payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)

        release = Release.objects.last()
        self.assertEqual(release.user, artist.owner)

    @responses.activate
    @mock.patch('releases.utils.tasks')
    def test_empty_royalty_splits_raises_validation_error(self, mocked_tasks):
        url = reverse('release-list')
        self.request_payload['songs'][0]['royalty_splits'] = []

        response = self.client.post(url, self.request_payload, format='json')
        self.assertEqual(
            response.status_code, status.HTTP_400_BAD_REQUEST, response.data
        )

        expected_error_message = (
            "The sum of the royalty splits' rates is not equal to 1"
        )
        returned_error_message = response.json()['songs'][0]['royalty_splits'][0]

        self.assertEqual(returned_error_message, expected_error_message)

    @responses.activate
    @mock.patch('releases.utils.tasks')
    def test_created_by_populated(self, mocked_tasks):
        url = reverse('release-list')
        response = self.client.post(url, self.request_payload, format='json')
        release = Release.objects.get(pk=response.data['id'])
        self.assertEqual(release.created_by, self.user)

    @responses.activate
    @mock.patch('releases.utils.tasks')
    def test_user_id_returned(self, mocked_tasks):
        url = reverse('release-list')
        response = self.client.post(url, self.request_payload, format='json')
        release = Release.objects.get(pk=response.data['id'])
        self.assertEqual(release.user.id, response.data['user_id'])

    @responses.activate
    @mock.patch('releases.utils.tasks')
    def test_writer_matching(self, mocked_tasks):
        url = reverse('release-list')
        response = self.client.post(url, self.request_payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        contributor_url = reverse('create-contributor-artist')
        test_cases = [
            'Writer Artist',
            'writer artista',
            'WRITER ARTIST',
            'write artist',
        ]
        for name in test_cases:
            contributor_payload = {"name": name}
            contributor_resp = self.client.post(
                contributor_url, contributor_payload, format='json'
            )
            self.assertEqual(contributor_resp.json()['id'], self.artist_3.id)

    @responses.activate
    @mock.patch('releases.utils.tasks')
    def test_preview_start_time_pro(self, mocked_tasks):
        url = reverse('release-list')
        payload = self.request_payload
        payload['songs'][0]['preview_start_time'] = 10
        payload['songs'][1]['preview_start_time'] = None
        response = self.client.post(url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['songs'][0]['preview_start_time'], 10)
        self.assertEqual(response.data['songs'][1]['preview_start_time'], None)

    @responses.activate
    @mock.patch('releases.utils.tasks')
    def test_preview_start_time_validator_value(self, mocked_tasks):
        url = reverse('release-list')
        payload = self.request_payload
        payload['songs'][0]['preview_start_time'] = -10
        expected_error_message = "Ensure this value is greater than or equal to 0."
        response = self.client.post(url, payload, format='json')
        return_error = response.json()['songs'][0]['preview_start_time'][0]
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(expected_error_message, return_error)

    @responses.activate
    @mock.patch('releases.utils.tasks')
    def test_main_primary_artist_sequence_is_always_one(self, mocked_tasks):
        url = reverse('release-list')
        payload = self.request_payload
        payload['songs'][0]['artists_roles'] = [
            {'roles': ['primary_artist', 'mixer'], 'artist_id': self.artist_2.id},
            {'roles': ['primary_artist', 'writer'], 'artist_id': self.artist_1.id},
            {'roles': ['featured_artist'], 'artist_id': self.artist_3.id},
            {'roles': ['writer', 'producer'], 'artist_id': self.artist_4.id},
        ]
        response = self.client.post(url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        roles_count = SongArtistRole.objects.filter(
            artist=self.artist_1,
            role=SongArtistRole.ROLE_PRIMARY_ARTIST,
            artist_sequence=1,
        ).count()

        self.assertEqual(roles_count, 2)

    @responses.activate
    @mock.patch('releases.utils.tasks')
    def test_artist_sequence_is_a_sequence(self, mocked_tasks):
        url = reverse('release-list')
        payload = self.request_payload
        payload['songs'][0]['artists_roles'] = [
            {'roles': ['primary_artist', 'mixer'], 'artist_id': self.artist_2.id},
            {'roles': ['primary_artist', 'writer'], 'artist_id': self.artist_1.id},
            {'roles': ['featured_artist'], 'artist_id': self.artist_3.id},
            {'roles': ['writer', 'producer'], 'artist_id': self.artist_4.id},
        ]
        response = self.client.post(url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        songs = Song.objects.all()

        sequence = list(
            SongArtistRole.objects.filter(song=songs[0]).values_list(
                'artist_sequence', flat=True
            )
        )

        self.assertEqual(sorted(sequence), list(range(1, 8)))

    @responses.activate
    @mock.patch('releases.utils.tasks')
    def test_main_primary_artist_is_created_first(self, mocked_tasks):
        """
        main_primary_artist with ROLE_PRIMARY_ARTIST needs to be created first
        as the dynamic logic in the XML generation for some stores ignores the
        artist_sequence and sets sequence based on .order_by("role", "created")
        """
        url = reverse('release-list')
        payload = self.request_payload
        payload['songs'][0]['artists_roles'] = [
            {'roles': ['primary_artist', 'mixer'], 'artist_id': self.artist_2.id},
            {'roles': ['primary_artist', 'writer'], 'artist_id': self.artist_1.id},
            {'roles': ['featured_artist'], 'artist_id': self.artist_3.id},
            {'roles': ['writer', 'producer'], 'artist_id': self.artist_4.id},
        ]
        response = self.client.post(url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        songs = Song.objects.all()

        main_primary_1 = SongArtistRole.objects.filter(song=songs[0]).first()
        main_primary_2 = SongArtistRole.objects.filter(song=songs[1]).first()

        self.assertEqual(main_primary_1.artist_id, self.artist_1.id)
        self.assertEqual(main_primary_1.role, SongArtistRole.ROLE_PRIMARY_ARTIST)
        self.assertEqual(main_primary_2.artist_id, self.artist_1.id)
        self.assertEqual(main_primary_2.role, SongArtistRole.ROLE_PRIMARY_ARTIST)


class ReleaseAPIUpdateReleaseDateTestCase(AmuseAPITestCase):
    def setUp(self):
        super(ReleaseAPIUpdateReleaseDateTestCase, self).setUp()

        StoreFactory(name='Spotify')
        StoreFactory(is_pro=True, name=Store.YOUTUBE_CONTENT_ID_STORE_NAME)
        StoreFactory(internal_name='youtube_music')
        tomorrow = timezone.now().date() + timedelta(days=1)
        user = UserFactory()
        artist_v2 = user.create_artist_v2('artist')
        release = ReleaseFactory(user=user, release_date=tomorrow)

        ReleaseArtistRole.objects.create(
            release=release,
            artist=artist_v2,
            role=ReleaseArtistRole.ROLE_PRIMARY_ARTIST,
            main_primary_artist=True,
        )

        self.user = user
        self.release = release
        self.artist_v2 = artist_v2

        self.client.credentials(HTTP_ACCEPT=API_V4_ACCEPT_VALUE)
        self.client.force_authenticate(self.user)

    def test_dont_allow_update_if_release_date_is_less_than_10_days_from_today(self):
        today = timezone.now().date()
        new_release_date = today + timedelta(days=9)

        response = self.client.patch(
            reverse('release-detail', args=[self.release.id]),
            data={'release_date': new_release_date.strftime('%Y-%m-%d')},
        )
        self.assertEqual(
            status.HTTP_400_BAD_REQUEST, response.status_code, response.json()
        )

    def test_allow_update_if_release_date_is_10_or_more_days_from_today(self):
        today = timezone.now().date()
        new_release_date = today + timedelta(days=10)

        response = self.client.patch(
            reverse('release-detail', args=[self.release.id]),
            data={'release_date': new_release_date.strftime('%Y-%m-%d')},
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code, response.json())

    def test_set_release_date_10_days_from_today_if_release_date_not_in_request(self):
        response = self.client.patch(reverse('release-detail', args=[self.release.id]))
        today = timezone.now().date()
        new_release_date = today + timedelta(days=10)

        data = response.json()
        self.assertEqual(status.HTTP_200_OK, response.status_code)
        self.assertEqual(new_release_date.strftime('%Y-%m-%d'), data['release_date'])

    def test_do_not_force_user_to_provide_release_date(self):
        release_date = timezone.now().date() + timedelta(days=123)

        release = ReleaseFactory(user=self.user, release_date=release_date)
        ReleaseArtistRole.objects.create(
            release=release,
            artist=self.artist_v2,
            role=ReleaseArtistRole.ROLE_PRIMARY_ARTIST,
            main_primary_artist=True,
        )

        response = self.client.patch(reverse('release-detail', args=[release.id]))
        data = response.json()
        self.assertEqual(status.HTTP_200_OK, response.status_code)
        self.assertEqual(release_date.strftime('%Y-%m-%d'), data['release_date'])


class ReleaseApiNotProTestCase(AmuseAPITestCase):
    def setUp(self):
        super(ReleaseApiNotProTestCase, self).setUp()
        self.user = UserFactory(artist_name='Lil Artist')
        self.user_2 = UserFactory()
        self.user_3 = UserFactory()
        self.user_4 = UserFactory()

        self.artist_1 = self.user.create_artist_v2(name='Lil Artist')
        self.artist_2 = self.user_2.create_artist_v2(name='FeaturedArtist')
        self.artist_3 = self.user_3.create_artist_v2(name='Writer Artist')
        self.artist_4 = self.user_4.create_artist_v2(name='ProducerdArtist')

        self.artists = dict()
        self.artists[self.artist_1.id] = self.artist_1
        self.artists[self.artist_2.id] = self.artist_2
        self.artists[self.artist_3.id] = self.artist_3
        self.artists[self.artist_4.id] = self.artist_4

        self.genre = GenreFactory()

        country_1 = CountryFactory()
        country_2 = CountryFactory()

        self.client.credentials(HTTP_ACCEPT=API_V4_ACCEPT_VALUE)
        self.client.force_authenticate(self.user)

        self.free_store = StoreFactory(name='Spotify')
        self.pro_store = StoreFactory(
            is_pro=True, name=Store.YOUTUBE_CONTENT_ID_STORE_NAME
        )
        StoreFactory(internal_name='youtube_music')
        UPCFactory(status=Code.STATUS_UNUSED)
        self.isrc = ISRCFactory(status=Code.STATUS_UNUSED)
        genre = GenreFactory()

        cover_art_storage = S3Storage(
            bucket_name=settings.AWS_COVER_ART_UPLOADED_BUCKET_NAME
        )
        cover_filename = 'cover.jpg'
        with cover_art_storage.open(cover_filename, 'wb') as f:
            f.write(open('amuse/tests/test_api/data/amuse.jpg', 'rb').read())
        self.release_date = timezone.now().date() + timedelta(days=30)

        self.request_payload = {
            'name': 'Postman Release (v4)',
            'label': None,
            'cover_art_filename': 'cover.jpg',
            'excluded_stores': [],
            'excluded_countries': [country_1.code, country_2.code],
            'upc': '',
            'artist_id': self.artist_1.id,
            'release_date': self.release_date.strftime('%Y-%m-%d'),
            'songs': [
                {
                    'name': 'Test Song 1',
                    'sequence': 1,
                    'version': 'Version Title',
                    'explicit': 'clean',
                    'recording_year': 2018,
                    'filename': 'users_filename.wav',
                    'origin': 'remix',
                    'isrc': '',
                    'audio_s3_key': 'wave.wav',
                    'youtube_content_id': 'none',
                    'cover_licensor': '',
                    'genre': {'id': genre.id, 'name': genre.name},
                    'artists_roles': [
                        {'roles': ['mixer', 'writer'], 'artist_id': self.artist_3.id},
                        {'roles': ['primary_artist'], 'artist_id': self.artist_1.id},
                        {'roles': ['featured_artist'], 'artist_id': self.artist_2.id},
                        {'roles': ['producer'], 'artist_id': self.artist_4.id},
                    ],
                    'royalty_splits': [{'user_id': self.user.id, 'rate': 1.0}],
                }
            ],
        }

    @responses.activate
    @mock.patch('releases.utils.tasks')
    def test_create_asap_release_non_pro_user_fail(self, mock):
        self.request_payload['schedule_type'] = Release.SCHEDULE_TYPES_MAP[
            Release.SCHEDULE_TYPE_ASAP
        ]
        expected_error_message = 'ASAP releases are a PRO feature'
        url = reverse('release-list')
        response = self.client.post(url, self.request_payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        error = response.data['non_field_errors'][0]
        assert error == expected_error_message

    @responses.activate
    @mock.patch('releases.utils.tasks')
    def test_create_static_release_invalid_schedule_type_fail(self, mock):
        self.request_payload['schedule_type'] = 'tomorrow'
        expected_error_message = 'Invalid schedule type: tomorrow'
        url = reverse('release-list')
        response = self.client.post(url, self.request_payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        error = response.data['schedule_type'][0]
        assert error == expected_error_message

    @responses.activate
    @mock.patch('releases.utils.tasks')
    def test_only_one_pending_release_allowed(self, mock):
        expected_error_message = 'Free user can only have one PENDING release'
        release = ReleaseFactory(
            user=self.user, created_by=self.user, status=Release.STATUS_PENDING
        )
        url = reverse('release-list')
        response = self.client.post(url, self.request_payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(expected_error_message, response.data['detail'])

    @responses.activate
    @mock.patch('releases.utils.tasks')
    def test_all_stores_excluded_assigns_free_stores(self, mock):
        inactive_pro_store = StoreFactory(active=False, is_pro=True, name='Napster')
        self.request_payload['excluded_store_ids'] = [
            self.pro_store.pk,
            self.free_store.pk,
        ]
        url = reverse('release-list')

        response = self.client.post(url, self.request_payload, format='json')
        release = Release.objects.last()

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(
            sorted(release.excluded_store_ids),
            sorted([self.pro_store.pk, inactive_pro_store.pk]),
        )

    @responses.activate
    @mock.patch('releases.utils.tasks')
    def test_label_is_pro_feature(self, mock):
        expected_error_message = 'Custom labels are a PRO feature'
        self.request_payload['label'] = 'XYZ Label Company'
        url = reverse('release-list')
        response = self.client.post(url, self.request_payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        error = response.data['non_field_errors'][0]
        assert error == expected_error_message

    @responses.activate
    @mock.patch('releases.utils.tasks')
    def test_pre_save_link_for_asap_release_non_pro_user_fail(self, mocked_tasks):
        expected_error_message = 'Pre-save links are not available to Start Users'
        url = reverse('release-list')
        self.request_payload['schedule_type'] = Release.SCHEDULE_TYPES_MAP[
            Release.SCHEDULE_TYPE_ASAP
        ]
        self.request_payload['include_pre_save_link'] = True
        response = self.client.post(url, self.request_payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        print(response.data)
        error = response.data['include_pre_save_link'][0]
        assert error == expected_error_message


class ReleaseApiPrimaryArtistValidator(AmuseAPITestCase):
    def setUp(self):
        super(ReleaseApiPrimaryArtistValidator, self).setUp()
        self.user = UserFactory(artist_name='Lil Artist')
        self.user_2 = UserFactory()
        self.user_3 = UserFactory()
        self.user_4 = UserFactory()

        self.artist_1 = self.user.create_artist_v2(name='Lil Artist')
        self.artist_2 = self.user_2.create_artist_v2(name='FeaturedArtist')
        self.artist_3 = self.user_3.create_artist_v2(name='Writer Artist')
        self.artist_4 = self.user_4.create_artist_v2(name='ProducerdArtist')

        self.artists = dict()
        self.artists[self.artist_1.id] = self.artist_1
        self.artists[self.artist_2.id] = self.artist_2
        self.artists[self.artist_3.id] = self.artist_3
        self.artists[self.artist_4.id] = self.artist_4

        self.genre = GenreFactory()

        country_1 = CountryFactory()
        country_2 = CountryFactory()

        self.client.credentials(HTTP_ACCEPT=API_V4_ACCEPT_VALUE)
        self.client.force_authenticate(self.user)

        StoreFactory(name='Spotify')
        StoreFactory(is_pro=True, name=Store.YOUTUBE_CONTENT_ID_STORE_NAME)
        StoreFactory(internal_name='youtube_music')
        UPCFactory(status=Code.STATUS_UNUSED)
        self.isrc = ISRCFactory(status=Code.STATUS_UNUSED)
        genre = GenreFactory()

        cover_art_storage = S3Storage(
            bucket_name=settings.AWS_COVER_ART_UPLOADED_BUCKET_NAME
        )
        cover_filename = 'cover.jpg'
        with cover_art_storage.open(cover_filename, 'wb') as f:
            f.write(open('amuse/tests/test_api/data/amuse.jpg', 'rb').read())
        self.release_date = timezone.now().date() + timedelta(days=30)

        self.request_payload = {
            'name': 'Postman Release (v4)',
            'label': None,
            'cover_art_filename': 'cover.jpg',
            'release_date': self.release_date.strftime('%Y-%m-%d'),
            'schedule_type': Release.SCHEDULE_TYPES_MAP[Release.SCHEDULE_TYPE_STATIC],
            'excluded_stores': [],
            'excluded_countries': [country_1.code, country_2.code],
            'upc': '',
            'artist_id': self.artist_1.id,
            'songs': [
                {
                    'name': 'Test Song 1',
                    'sequence': 1,
                    'version': 'Version Title',
                    'explicit': 'clean',
                    'recording_year': 2018,
                    'filename': 'users_filename.wav',
                    'origin': 'remix',
                    'isrc': '',
                    'audio_s3_key': 'wave.wav',
                    'youtube_content_id': 'none',
                    'cover_licensor': '',
                    'genre': {'id': genre.id, 'name': genre.name},
                    'artists_roles': [
                        {'roles': ['mixer', 'writer'], 'artist_id': self.artist_3.id},
                        {'roles': ['featured_artist'], 'artist_id': self.artist_2.id},
                        {'roles': ['producer'], 'artist_id': self.artist_4.id},
                    ],
                    'royalty_splits': [{'user_id': self.user.id, 'rate': 1.0}],
                }
            ],
        }

    @responses.activate
    @mock.patch('releases.utils.tasks')
    def test_song_primary_artist_validator(self, mock):
        expected_error_message = 'Song must have primary_artist role'
        url = reverse('release-list')
        response = self.client.post(url, self.request_payload, format='json')
        response_data = response.json()
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEquals(expected_error_message, response_data['songs'][0])

    @responses.activate
    @mock.patch('releases.utils.tasks')
    def test_main_primary_artist_with_invalid_role_raises_error(self, mock):
        url = reverse('release-list')
        self.request_payload['songs'][0]['artists_roles'].append(
            {'roles': ['primary_artist'], 'artist_id': self.artist_2.id}
        )
        self.request_payload['songs'][0]['artists_roles'].append(
            {'roles': ['featured_artist'], 'artist_id': self.artist_1.id}
        )
        response = self.client.post(url, self.request_payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(
            'Main primary artist missing from track.',
            response.json()['non_field_errors'][0],
        )

    @responses.activate
    @mock.patch('releases.utils.tasks')
    def test_main_primary_artist_missing_role_raises_error(self, mock):
        url = reverse('release-list')
        self.request_payload['songs'][0]['artists_roles'].append(
            {'roles': ['primary_artist'], 'artist_id': self.artist_2.id}
        )
        response = self.client.post(url, self.request_payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(
            'Main primary artist missing from track.',
            response.json()['non_field_errors'][0],
        )
