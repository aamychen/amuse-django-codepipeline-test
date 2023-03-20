import copy
from datetime import timedelta
from unittest import mock

from django.conf import settings
from django.urls import reverse_lazy as reverse
from django.utils import timezone
import responses
from rest_framework import status

from amuse.storages import S3Storage
from amuse.tests.test_api.base import API_V4_ACCEPT_VALUE, AmuseAPITestCase
from codes.models import Code
from codes.tests.factories import ISRCFactory, UPCFactory
from countries.tests.factories import CountryFactory
from releases.models import Release, Song, Store
from releases.tests.factories import GenreFactory, StoreFactory
from subscriptions.models import Subscription, SubscriptionPlan
from subscriptions.tests.factories import SubscriptionFactory, SubscriptionPlanFactory
from users.models import User
from users.tests.factories import UserFactory


class ReleaseApiPlusTierTestCase(AmuseAPITestCase):
    def setUp(self):
        super(ReleaseApiPlusTierTestCase, self).setUp()
        self.user = UserFactory(artist_name='Lil Artist')
        self.sub_plan = SubscriptionPlanFactory(tier=SubscriptionPlan.TIER_PLUS)
        self.subscription = SubscriptionFactory(user=self.user, plan=self.sub_plan)

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
                    'royalty_splits': [{'user_id': self.user.id, 'rate': 1.0}],
                }
            ],
        }

    def expire_sub_and_refresh(self):
        self.subscription.status = Subscription.STATUS_EXPIRED
        self.subscription.save()
        self.subscription.refresh_from_db()
        self.user.refresh_from_db()

    @responses.activate
    @mock.patch('releases.utils.tasks')
    def test_preview_start_time(self, mocked_tasks):
        assert self.user.tier == SubscriptionPlan.TIER_PLUS
        url = reverse('release-list')
        payload = self.request_payload
        payload['songs'][0]['preview_start_time'] = 10
        response = self.client.post(url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['songs'][0]['preview_start_time'], 10)
        print(response.data)

    @responses.activate
    @mock.patch('releases.utils.tasks')
    def test_preview_start_time_permissions(self, mocked_tasks):
        self.expire_sub_and_refresh()
        assert self.user.tier == User.TIER_FREE
        url = reverse('release-list')
        payload = self.request_payload
        payload['songs'][0]['preview_start_time'] = 10
        response = self.client.post(url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    @responses.activate
    @mock.patch('releases.utils.tasks')
    def test_no_stores_excluded_for_plus_user(self, mocked_tasks):
        assert self.user.tier == SubscriptionPlan.TIER_PLUS
        url = reverse('release-list')
        payload = self.request_payload
        response = self.client.post(url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        assert response.data['excluded_stores'] == []

    @responses.activate
    @mock.patch('releases.utils.tasks')
    def test_yt_content_id_allowed_to_plus_tier(self, mocked_tasks):
        assert self.user.tier == SubscriptionPlan.TIER_PLUS
        url = reverse('release-list')
        request_payload = copy.deepcopy(self.request_payload)
        request_payload['songs'][0]['youtube_content_id'] = 'monetize'
        response = self.client.post(url, request_payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        release = Release.objects.get(pk=response.data['id'])
        song = release.songs.all()[0]
        self.assertEqual(song.youtube_content_id, Song.YT_CONTENT_ID_MONETIZE)
        self.assertEqual(list(release.excluded_store_ids), [])

    @responses.activate
    @mock.patch('releases.utils.tasks')
    def test_yt_content_id_allowed_free_user(self, mocked_tasks):
        self.expire_sub_and_refresh()
        assert self.user.tier == User.TIER_FREE
        url = reverse('release-list')
        request_payload = copy.deepcopy(self.request_payload)
        request_payload['songs'][0]['youtube_content_id'] = 'monetize'
        response = self.client.post(url, request_payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        release = Release.objects.get(pk=response.data['id'])
        song = release.songs.all()[0]
        self.assertEqual(song.youtube_content_id, Song.YT_CONTENT_ID_MONETIZE)

    @responses.activate
    @mock.patch('releases.utils.tasks')
    def test_release_date_plus_tier(self, mocked_tasks):
        assert self.user.tier == SubscriptionPlan.TIER_PLUS
        url = reverse('release-list')
        request_payload = copy.deepcopy(self.request_payload)
        self.release_date = timezone.now().date() + timedelta(days=10)
        request_payload['release_date'] = self.release_date.strftime('%Y-%m-%d')
        response = self.client.post(url, request_payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(
            response.data['release_date'], self.release_date.strftime('%Y-%m-%d')
        )

    @responses.activate
    @mock.patch('releases.utils.tasks')
    def test_release_date_plus_tier_validation(self, mocked_tasks):
        assert self.user.tier == SubscriptionPlan.TIER_PLUS
        earliest_date = timezone.now().date() + timedelta(days=10)
        error_message = "Earliest release date possible is %s" % earliest_date
        url = reverse('release-list')
        request_payload = copy.deepcopy(self.request_payload)
        self.release_date = timezone.now().date() + timedelta(days=3)
        request_payload['release_date'] = self.release_date.strftime('%Y-%m-%d')
        response = self.client.post(url, request_payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(str(response.data['release_date'][0]), error_message)
