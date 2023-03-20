from datetime import date, timedelta
from decimal import Decimal
from unittest import mock

import responses
from django.conf import settings
from django.urls import reverse_lazy as reverse
from django.utils import timezone
from rest_framework import status

from amuse.api.base.views.exceptions import ProPermissionError
from amuse.storages import S3Storage
from amuse.tests.helpers import release_V4_payload
from amuse.tests.test_api.base import API_V4_ACCEPT_VALUE, AmuseAPITestCase
from codes.models import Code
from codes.tests.factories import ISRCFactory
from releases.models import Release, ReleaseArtistRole, RoyaltySplit, Store
from releases.tests.factories import (
    GenreFactory,
    ReleaseArtistRoleFactory,
    ReleaseFactory,
    RoyaltySplitFactory,
    SongFactory,
    StoreFactory,
)
from users.models import RoyaltyInvitation
from users.tests.factories import Artistv2Factory, RoyaltyInvitationFactory, UserFactory


class PaywallFreeBackendValidationTestCase(AmuseAPITestCase):
    def setUp(self):
        StoreFactory(name='Spotify')
        yt_cid_store = StoreFactory(
            is_pro=True, name=Store.YOUTUBE_CONTENT_ID_STORE_NAME
        )
        StoreFactory(internal_name='youtube_music')

        self.user = UserFactory(is_pro=False)
        self.user2 = UserFactory(is_pro=False)
        self.client.credentials(HTTP_ACCEPT=API_V4_ACCEPT_VALUE)
        self.client.force_authenticate(user=self.user)

        self.artist = self.user.create_artist_v2(name='Free Carola')
        self.release_payload = release_V4_payload(
            self.artist, self.artist, GenreFactory()
        )
        ISRCFactory(status=Code.STATUS_UNUSED)

        cover_art_storage = S3Storage(
            bucket_name=settings.AWS_COVER_ART_UPLOADED_BUCKET_NAME
        )
        cover_filename = 'cover.jpg'
        with cover_art_storage.open(cover_filename, 'wb') as f:
            f.write(open('amuse/tests/test_api/data/amuse.jpg', 'rb').read())

        audio_upload_storage = S3Storage(
            bucket_name=settings.AWS_SONG_FILE_UPLOADED_BUCKET_NAME
        )
        with audio_upload_storage.open('wave.wav', 'w') as f:
            f.write(open('amuse/tests/test_api/data/wave.wav', 'rb').read())

    def assert_pro_permission_error(self, response):
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(
            str(response.data['detail']), ProPermissionError.default_detail
        )
        self.assertEqual(response.data['detail'].code, ProPermissionError.default_code)

    @responses.activate
    @mock.patch('releases.utils.tasks')
    def test_pro_stores_are_excluded_automatically(self, mock_tasks):
        pro_store_1 = StoreFactory(is_pro=True)
        pro_store_2 = StoreFactory(is_pro=True)
        StoreFactory(is_pro=False)
        StoreFactory(is_pro=False)

        url = reverse('release-list')
        response = self.client.post(url, self.release_payload, format='json')

        assert sorted(response.data["excluded_stores"]) == sorted(
            [pro_store_1.id, pro_store_2.id, Store.get_yt_content_id_store().pk]
        )
        assert Release.objects.count() == 1

    @responses.activate
    @mock.patch('releases.utils.tasks')
    def test_cannot_use_pro_stores_but_can_use_free_if_pro_stores_are_excluded(
        self, mock_tasks
    ):
        pro_store = StoreFactory(is_pro=True)
        pro_store2 = StoreFactory(is_pro=True)
        StoreFactory(is_pro=False)
        StoreFactory(is_pro=False)

        self.release_payload['excluded_stores'] = [pro_store.id, pro_store2.id]

        url = reverse('release-list')
        response = self.client.post(url, self.release_payload, format='json')

        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.json())
        assert Release.objects.count() == 1
        self.assertEqual(
            sorted(Release.objects.first().excluded_store_ids),
            sorted([pro_store.id, pro_store2.id, Store.get_yt_content_id_store().pk]),
        )

    @responses.activate
    @mock.patch('releases.utils.tasks')
    def test_can_use_free_with_no_pro_stores(self, mock_tasks):
        StoreFactory(is_pro=False)
        StoreFactory(is_pro=False)

        url = reverse('release-list')
        response = self.client.post(url, self.release_payload, format='json')

        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.json())
        assert Release.objects.count() == 1

    @mock.patch('releases.utils.tasks')
    def test_youtube_content_id_is_excluded_automatically(self, mock_tasks):
        url = reverse('release-list')
        response = self.client.post(url, self.release_payload, format='json')
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["excluded_stores"] == [Store.get_yt_content_id_store().pk]
        assert Release.objects.count() == 1

    @mock.patch('releases.utils.tasks')
    def test_cannot_use_express_delivery(self, mock_tasks):
        url = reverse('release-list')
        release_date = timezone.now().date() + timedelta(days=10)
        release_payload = release_V4_payload(
            self.artist, self.artist, GenreFactory(), release_date
        )

        response = self.client.post(url, release_payload, format='json')

        self.assertEqual(
            response.status_code, status.HTTP_400_BAD_REQUEST, response.json()
        )
        assert 'Earliest release date possible is' in response.json()['release_date'][0]
        self.assertEqual(Release.objects.count(), 0)

    @mock.patch('releases.utils.tasks')
    def test_release_date_21_days_from_now_not_allowed(self, mock_tasks):
        url = reverse('release-list')
        release_date = timezone.now().date() + timedelta(days=21)
        release_payload = release_V4_payload(
            self.artist, self.artist, GenreFactory(), release_date
        )

        response = self.client.post(url, release_payload, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(Release.objects.count(), 0)

    @mock.patch('releases.utils.tasks')
    def test_release_date_29_days_from_now_allowed(self, mock_tasks):
        url = reverse('release-list')
        release_date = timezone.now().date() + timedelta(days=29)
        release_payload = release_V4_payload(
            self.artist, self.artist, GenreFactory(), release_date
        )

        response = self.client.post(url, release_payload, format='json')

        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.json())
        self.assertEqual(Release.objects.count(), 1)

    @responses.activate
    @mock.patch("users.helpers.cioevents")
    def test_can_update_splits(self, mocked_cioevents):
        """
        As of PLAT-184 (https://amuseio.atlassian.net/browse/PLAT-184) splits are now
        available to free users as well. Creating splits and updating them is allowed.
        """
        release = ReleaseFactory(user=self.user)
        ReleaseArtistRoleFactory(
            artist=self.artist,
            release=release,
            role=ReleaseArtistRole.ROLE_PRIMARY_ARTIST,
            main_primary_artist=True,
        )
        song = SongFactory(release=release)

        royalty_split = RoyaltySplitFactory(
            user=self.user,
            song=song,
            rate=1.0,
            status=RoyaltySplit.STATUS_ACTIVE,
            revision=0,
            start_date=None,
            end_date=None,
        )
        payload = [
            {'user_id': self.user.id, 'rate': 0.5},
            {'user_id': self.user2.id, 'rate': 0.5},
        ]

        url = reverse('update-royalty-splits', args=(song.id,))
        response = self.client.put(url, payload, format='json')

        assert response.status_code == status.HTTP_200_OK

    @responses.activate
    @mock.patch('releases.utils.tasks')
    def test_can_create_multi_user_royaltysplit(self, mock_tasks):
        self.release_payload['songs'][0]['royalty_splits'] = [
            {'user_id': self.user.id, 'rate': 0.75},
            {'user_id': self.user2.id, 'rate': 0.25},
        ]
        url = reverse('release-list')
        response = self.client.post(url, self.release_payload, format='json')
        assert response.status_code == status.HTTP_201_CREATED
        assert Release.objects.count() == 1

    @responses.activate
    @mock.patch('releases.utils.tasks')
    def test_can_create_non_owner_100_percent_split(self, mock_tasks):
        self.artist.owner = self.user2
        self.artist.save()
        url = reverse('release-list')
        response = self.client.post(url, self.release_payload, format='json')
        assert response.status_code == status.HTTP_201_CREATED
        assert Release.objects.count() == 1

    @responses.activate
    @mock.patch('releases.utils.tasks')
    def test_can_create_owner_royaltysplit_100_percent_split(self, mock_tasks):
        """
        Note that we only allow a Free user to create a 100% split for a song for the
        OWNER of the artist that is the main_primary_artist
        (i.e. the artist that the release is created “for)
        """
        self.artist.owner = self.user2
        self.artist.save()
        self.release_payload['songs'][0]['royalty_splits'] = [
            {'user_id': self.artist.owner.id, 'rate': 1.00}
        ]
        url = reverse('release-list')
        response = self.client.post(url, self.release_payload, format='json')
        assert response.status_code == status.HTTP_201_CREATED
        assert Release.objects.count() == 1

    def test_can_accept_royaltysplit(self):
        """
        We will however charge a 15% commission fee on their splits if they don’t
        subscribe to Pro, but that’s handled in the new revenue system
        """
        release = ReleaseFactory(user=self.user)
        song = SongFactory(release=release)
        artist = Artistv2Factory(owner=self.user)
        ReleaseArtistRoleFactory(
            artist=artist, release=release, main_primary_artist=True
        )
        RoyaltySplitFactory(song=song, user=self.user, rate=Decimal('0.5'))

        invitation = RoyaltyInvitationFactory(
            inviter=self.user,
            invitee=self.user2,
            token="123",
            status=RoyaltyInvitation.STATUS_PENDING,
            royalty_split=RoyaltySplitFactory(
                song=song, rate=Decimal('0.5'), start_date=date.today()
            ),
            last_sent=timezone.now(),
        )

        self.client.force_authenticate(user=self.user2)
        url = reverse('royaltyinvitation-confirm')
        data = {'token': "123"}
        response = self.client.post(url, data, format='json')

        invitation.refresh_from_db()
        invitation.royalty_split.refresh_from_db()

        assert response.status_code == status.HTTP_202_ACCEPTED
        assert invitation.status == RoyaltyInvitation.STATUS_ACCEPTED
        assert invitation.royalty_split.status == RoyaltySplit.STATUS_CONFIRMED


class PaywallProBackendValidationTestCase(AmuseAPITestCase):
    def setUp(self):
        yt_cid_store = StoreFactory(
            is_pro=True, name=Store.YOUTUBE_CONTENT_ID_STORE_NAME
        )
        StoreFactory(internal_name='youtube_music')

        self.user = UserFactory(is_pro=True)
        self.user2 = UserFactory(is_pro=True)
        self.client.credentials(HTTP_ACCEPT=API_V4_ACCEPT_VALUE)
        self.client.force_authenticate(user=self.user)

        self.artist = self.user.create_artist_v2(name='Pro Carola')
        self.release_payload = release_V4_payload(
            self.artist, self.artist, GenreFactory()
        )
        ISRCFactory(status=Code.STATUS_UNUSED)

        cover_art_storage = S3Storage(
            bucket_name=settings.AWS_COVER_ART_UPLOADED_BUCKET_NAME
        )
        cover_filename = 'cover.jpg'
        with cover_art_storage.open(cover_filename, 'wb') as f:
            f.write(open('amuse/tests/test_api/data/amuse.jpg', 'rb').read())

    @responses.activate
    @mock.patch('releases.utils.tasks')
    def test_can_use_pro_stores(self, mock_tasks):
        StoreFactory(is_pro=True)
        StoreFactory(is_pro=False)

        url = reverse('release-list')
        response = self.client.post(url, self.release_payload, format='json')

        assert response.status_code == status.HTTP_201_CREATED
        assert Release.objects.count() == 1

    @mock.patch('releases.utils.tasks')
    def test_can_use_youtube_content_id(self, mock_tasks):
        url = reverse('release-list')
        response = self.client.post(url, self.release_payload, format='json')
        assert response.status_code == status.HTTP_201_CREATED
        assert Release.objects.count() == 1
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Release.objects.count(), 1)

    @mock.patch('releases.utils.tasks')
    def test_can_use_express_delivery(self, mock_tasks):
        url = reverse('release-list')
        release_date = timezone.now().date() + timedelta(days=10)
        release_payload = release_V4_payload(
            self.artist, self.artist, GenreFactory(), release_date
        )

        response = self.client.post(url, release_payload, format='json')

        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.json())
        self.assertEqual(Release.objects.count(), 1)

    @mock.patch('releases.utils.tasks')
    def test_release_earlier_than_10_days_from_now_not_allowed(self, mock_tasks):
        url = reverse('release-list')
        release_date = timezone.now().date() + timedelta(days=5)
        release_payload = release_V4_payload(
            self.artist, self.artist, GenreFactory(), release_date
        )

        response = self.client.post(url, release_payload, format='json')

        self.assertEqual(
            response.status_code, status.HTTP_400_BAD_REQUEST, response.json()
        )
        assert 'Earliest release date possible is' in response.json()['release_date'][0]
        self.assertEqual(Release.objects.count(), 0)

    @responses.activate
    @mock.patch("users.helpers.cioevents")
    def test_can_update_splits(self, mocked_cioevents):
        release = ReleaseFactory(user=self.user)
        ReleaseArtistRoleFactory(
            artist=self.artist,
            release=release,
            role=ReleaseArtistRole.ROLE_PRIMARY_ARTIST,
            main_primary_artist=True,
        )
        song = SongFactory(release=release)

        royalty_split = RoyaltySplitFactory(
            user=self.user,
            song=song,
            rate=1.0,
            status=RoyaltySplit.STATUS_ACTIVE,
            revision=0,
            start_date=None,
            end_date=None,
        )
        payload = [
            {'user_id': self.user.id, 'rate': 0.5},
            {'user_id': self.user2.id, 'rate': 0.5},
        ]

        url = reverse('update-royalty-splits', args=(song.id,))
        response = self.client.put(url, payload, format='json')

        assert response.status_code == status.HTTP_200_OK

    @responses.activate
    @mock.patch('releases.utils.tasks')
    def test_can_create_multi_user_royaltysplit(self, mock_tasks):
        self.release_payload['songs'][0]['royalty_splits'] = [
            {'user_id': self.user.id, 'rate': 0.75},
            {'user_id': self.user2.id, 'rate': 0.25},
        ]
        url = reverse('release-list')
        response = self.client.post(url, self.release_payload, format='json')
        assert response.status_code == status.HTTP_201_CREATED
        assert Release.objects.count() == 1

    @responses.activate
    @mock.patch('releases.utils.tasks')
    def test_can_create_non_owner_royaltysplit_100_percent_split(self, mock_tasks):
        self.artist.owner = self.user2
        self.artist.save()
        url = reverse('release-list')
        response = self.client.post(url, self.release_payload, format='json')
        assert response.status_code == status.HTTP_201_CREATED
        assert Release.objects.count() == 1

    @responses.activate
    @mock.patch('releases.utils.tasks')
    def test_can_create_owner_royaltysplit_100_percent_split(self, mock_tasks):
        self.artist.owner = self.user2
        self.artist.save()
        self.release_payload['songs'][0]['royalty_splits'] = [
            {'user_id': self.artist.owner.id, 'rate': 1.00}
        ]
        url = reverse('release-list')
        response = self.client.post(url, self.release_payload, format='json')
        assert response.status_code == status.HTTP_201_CREATED
        assert Release.objects.count() == 1

    def test_can_accept_royaltysplit(self):
        release = ReleaseFactory(user=self.user)
        song = SongFactory(release=release)
        artist = Artistv2Factory(owner=self.user)
        ReleaseArtistRoleFactory(
            artist=artist, release=release, main_primary_artist=True
        )
        RoyaltySplitFactory(song=song, user=self.user, rate=Decimal('0.5'))

        invitation = RoyaltyInvitationFactory(
            inviter=self.user,
            invitee=self.user2,
            token="123",
            status=RoyaltyInvitation.STATUS_PENDING,
            royalty_split=RoyaltySplitFactory(
                song=song, rate=Decimal('0.5'), start_date=date.today()
            ),
            last_sent=timezone.now(),
        )

        self.client.force_authenticate(user=self.user2)
        url = reverse('royaltyinvitation-confirm')
        data = {'token': "123"}
        response = self.client.post(url, data, format='json')

        invitation.refresh_from_db()
        invitation.royalty_split.refresh_from_db()

        assert response.status_code == status.HTTP_202_ACCEPTED
        assert invitation.status == RoyaltyInvitation.STATUS_ACCEPTED
        assert invitation.royalty_split.status == RoyaltySplit.STATUS_CONFIRMED
