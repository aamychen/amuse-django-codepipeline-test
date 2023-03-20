from datetime import date
from unittest.mock import patch

import responses
from django.conf import settings
from django.urls import reverse_lazy as reverse
from freezegun import freeze_time
from rest_framework import status

from amuse.api.v4.serializers.helpers import get_serialized_royalty_splits
from amuse.storages import S3Storage
from amuse.tests.test_api.base import (
    API_V2_ACCEPT_VALUE,
    API_V4_ACCEPT_VALUE,
    AmuseAPITestCase,
)
from releases.models import ReleaseArtistRole
from releases.models.royalty_split import RoyaltySplit
from releases.tests.factories import (
    CoverArtFactory,
    ReleaseArtistRoleFactory,
    ReleaseFactory,
    RoyaltySplitFactory,
    SongArtistRoleFactory,
    SongFactory,
)
from users.models import RoyaltyInvitation, UserArtistRole
from users.tests.factories import (
    Artistv2Factory,
    RoyaltyInvitationFactory,
    UserArtistRoleFactory,
    UserFactory,
)


SOURCE_FILE_NAME = 'b03bcf60-e6ae-11e8-a8eb-c73a387ba237.jpg'
THUMB_FILE_NAME = 'b03bcf60-e6ae-11e8-a8eb-c73a387ba237.800x800.jpg'


class TestSplitPerRelaseUserHasAccessTestCase(AmuseAPITestCase):
    def setUp(self):
        self.user = UserFactory()

        self.client.credentials(HTTP_ACCEPT=API_V4_ACCEPT_VALUE)
        self.client.force_authenticate(user=self.user)

        self.release = ReleaseFactory(user=self.user, created_by=self.user)
        self.song = SongFactory(release=self.release)

        self.release_featured_artist = Artistv2Factory(name='Featured')
        self.release_main_primary_artist = Artistv2Factory(name='MPA')
        self.user_artist_spectator = Artistv2Factory(name='Spectator')

        # IMPORTANT: featured artist is created before main_primary_artist
        ReleaseArtistRoleFactory(
            release=self.release,
            artist=self.release_featured_artist,
            role=ReleaseArtistRole.ROLE_FEATURED_ARTIST,
            main_primary_artist=False,
        )
        ReleaseArtistRoleFactory(
            release=self.release,
            artist=self.release_main_primary_artist,
            role=ReleaseArtistRole.ROLE_PRIMARY_ARTIST,
            main_primary_artist=True,
        )

        UserArtistRoleFactory(
            user=self.user,
            artist=self.user_artist_spectator,
            type=UserArtistRole.SPECTATOR,
        )
        UserArtistRoleFactory(
            user=self.user,
            artist=self.release_main_primary_artist,
            type=UserArtistRole.OWNER,
        )

    def test_user_has_permissions(self):
        """
        Main primary artist (MPA) should be used to determine if user has permission to
        access the split. There was a bug, where first created artist (from release
        artist roles) was used to figure out if user has permission or not.
        Usually MPA is the first artist and in that case everything was
        working as expected. However, sometimes MPA is not first. This test case will
        ensure the MPA (not the first artist) is used in every case to determine
        if user has permission or not.
        :return:
        """
        url = reverse('royalty-splits-per-release', args=(self.release.id,))
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)


class RoyaltySplitAPIListTestCase(AmuseAPITestCase):
    def setUp(self):
        super().setUp()

        self.user_1 = UserFactory(
            first_name="Mister",
            last_name="Spliter",
            profile_photo="https://profile_photo.com/photo.jpg",
        )
        self.user_2 = UserFactory()
        self.user_3 = UserFactory()
        self.user_4 = UserFactory()
        self.artist = Artistv2Factory(name="Release Owner")
        UserArtistRoleFactory(user=self.user_1, artist=self.artist)
        UserArtistRoleFactory(
            user=self.user_3, artist=self.artist, type=UserArtistRole.ADMIN
        )
        UserArtistRoleFactory(
            user=self.user_4, artist=self.artist, type=UserArtistRole.MEMBER
        )

        self.client.credentials(HTTP_ACCEPT=API_V4_ACCEPT_VALUE)
        self.client.force_authenticate(user=self.user_1)

        self.release = ReleaseFactory(user=self.user_1)
        self.release.original_release_date = date(2018, 1, 1)
        self.release.save()
        self.release.refresh_from_db()
        self.song = SongFactory(release=self.release)
        self.primary_artist = Artistv2Factory()
        SongArtistRoleFactory(artist=self.primary_artist, song=self.song)
        self.song2 = SongFactory(release=self.release)

        storage = S3Storage(bucket_name=settings.AWS_COVER_ART_UPLOADED_BUCKET_NAME)
        with storage.open(SOURCE_FILE_NAME, 'wb') as file:
            file.write(
                open('amuse/tests/test_tasks/fixtures/amuse-cover.jpg', 'rb').read()
            )

        with patch('releases.models.coverart.CoverArt.save_jpeg_image'):
            self.cover_art = CoverArtFactory(
                release=self.release, file=SOURCE_FILE_NAME
            )
        ReleaseArtistRoleFactory(
            release=self.release, artist=self.artist, main_primary_artist=True
        )

        RoyaltySplitFactory(
            user=self.user_1,
            song=self.song,
            rate=1.0,
            status=RoyaltySplit.STATUS_ARCHIVED,
            start_date=None,
            end_date=date(2020, 1, 10),
            revision=1,
        )
        RoyaltySplitFactory(
            user=self.user_1,
            song=self.song,
            rate=0.7,
            status=RoyaltySplit.STATUS_ACTIVE,
            start_date=date(2020, 1, 11),
            end_date=None,
            revision=2,
        )
        RoyaltySplitFactory(
            user=self.user_2,
            song=self.song,
            rate=0.3,
            status=RoyaltySplit.STATUS_ACTIVE,
            start_date=date(2020, 1, 11),
            end_date=None,
            revision=2,
        )
        rs1 = RoyaltySplitFactory(
            user=None,
            song=self.song,
            rate=1.0,
            status=RoyaltySplit.STATUS_PENDING,
            start_date=date(2020, 1, 15),
            end_date=None,
            revision=3,
        )
        RoyaltyInvitationFactory(royalty_split=rs1)

    def test_correct_splits_returns_expected_data(self):
        url = reverse('royalty-splits')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        response_json = response.json()
        assert len(response_json) == 1

        self.assertTrue(response_json[0]['id'])
        self.assertEqual(response_json[0]['rate'], 0.7)
        self.assertEqual(response_json[0]['status'], RoyaltySplit.STATUS_ACTIVE)
        self.assertEqual(response_json[0]['song_name'], self.song.name)
        self.assertEqual(response_json[0]['song_isrc'], self.song.isrc.code)
        self.assertEqual(response_json[0]['artist_name'], self.primary_artist.name)
        self.assertIn(THUMB_FILE_NAME, response_json[0]['cover_art'])

    def test_splits_filtered_correctly(self):
        # conditions for returning a split:
        # status is ACTIVE or CONFIRMED
        # release not owned by the user
        # OR
        # split rate under 100

        # not shown - release owned by the user and rate is 1.0
        song1 = SongFactory(release=self.release)
        split1 = RoyaltySplitFactory(
            user=self.user_1,
            song=song1,
            rate=1.0,
            status=RoyaltySplit.STATUS_ACTIVE,
            start_date=None,
            end_date=None,
            revision=1,
        )

        # shown - release owned by the user and rate is less than 1.0
        song2 = SongFactory(release=self.release)
        split2 = RoyaltySplitFactory(
            user=self.user_1,
            song=song2,
            rate=0.9,
            status=RoyaltySplit.STATUS_ACTIVE,
            start_date=None,
            end_date=None,
            revision=1,
        )

        # shown - release owned by the user and rate is less than 1.0
        # status is CONFIRMED
        song3 = SongFactory(release=self.release)
        split3 = RoyaltySplitFactory(
            user=self.user_1,
            song=song3,
            rate=0.9,
            status=RoyaltySplit.STATUS_CONFIRMED,
            start_date=None,
            end_date=None,
            revision=1,
        )

        release = ReleaseFactory()
        release.original_release_date = date(2018, 1, 1)
        release.save()
        release.refresh_from_db()
        song = SongFactory(release=release)

        storage = S3Storage(bucket_name=settings.AWS_COVER_ART_UPLOADED_BUCKET_NAME)
        with storage.open(SOURCE_FILE_NAME, 'wb') as file:
            file.write(
                open('amuse/tests/test_tasks/fixtures/amuse-cover.jpg', 'rb').read()
            )
        cover_art = CoverArtFactory(release=release, file=SOURCE_FILE_NAME)

        # shown - release not owned by the user and rate is 1.0
        song4 = SongFactory(release=release)
        split4 = RoyaltySplitFactory(
            user=self.user_1,
            song=song4,
            rate=1.0,
            status=RoyaltySplit.STATUS_ACTIVE,
            start_date=None,
            end_date=None,
            revision=1,
        )

        url = reverse('royalty-splits')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        response_json_sorted = sorted(response.json(), key=lambda k: k['id'])
        assert len(response_json_sorted) == 4

        self.assertTrue(response_json_sorted[0]['id'])
        self.assertEqual(response_json_sorted[1]['id'], split2.id)
        self.assertEqual(response_json_sorted[2]['id'], split3.id)
        self.assertEqual(response_json_sorted[3]['id'], split4.id)

    def test_no_splits_returns_empty_list(self):
        RoyaltySplit.objects.all().delete()
        RoyaltyInvitation.objects.all().delete()
        url = reverse('royalty-splits')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json(), [])

    def test_unsupported_api_version_returns_error(self):
        self.client.credentials(HTTP_ACCEPT=API_V2_ACCEPT_VALUE)
        url = reverse('royalty-splits')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_get_splits_by_release(self):
        self.client.credentials(HTTP_ACCEPT=API_V4_ACCEPT_VALUE)
        url = reverse('royalty-splits-per-release', args=(self.release.id,))
        responses = self.client.get(url)
        data = responses.json()

        self.assertEqual(len(data), 4)
        self.assertEqual(data[0]['rate'], 1.0)
        self.assertEqual(data[0]['status'], RoyaltySplit.STATUS_ARCHIVED)
        self.assertEqual(data[0]['user_id'], self.release.user.id)
        self.assertEqual(data[0]['first_name'], self.release.user.first_name)
        self.assertEqual(data[0]['last_name'], self.release.user.last_name)
        self.assertEqual(data[0]['profile_photo'], self.release.user.profile_photo)
        self.assertEqual(data[0]['song_id'], self.song.id)
        self.assertEqual(
            data[0]['start_date'],
            self.release.original_release_date.strftime("%Y-%m-%d"),
        )

    def test_get_splits_by_release_permissions(self):
        self.client.credentials(HTTP_ACCEPT=API_V4_ACCEPT_VALUE)
        self.client.force_authenticate(user=self.user_2)
        url = reverse('royalty-splits-per-release', args=(self.release.id,))
        responses = self.client.get(url)
        self.assertEqual(responses.status_code, status.HTTP_403_FORBIDDEN)

    def test_get_splits_by_release_permissions_admin(self):
        self.client.credentials(HTTP_ACCEPT=API_V4_ACCEPT_VALUE)
        self.client.force_authenticate(user=self.user_3)
        url = reverse('royalty-splits-per-release', args=(self.release.id,))
        responses = self.client.get(url)
        self.assertEqual(responses.status_code, status.HTTP_200_OK)

    def test_get_splits_by_release_permissions_member(self):
        self.client.credentials(HTTP_ACCEPT=API_V4_ACCEPT_VALUE)
        self.client.force_authenticate(user=self.user_4)
        url = reverse('royalty-splits-per-release', args=(self.release.id,))
        responses = self.client.get(url)
        self.assertEqual(responses.status_code, status.HTTP_200_OK)


class RoyaltySplitAPIUpdateTestCase(AmuseAPITestCase):
    def setUp(self):
        super().setUp()

        with freeze_time("2020-01-10"):
            self.user_1 = UserFactory(is_pro=True)
            self.user_2 = UserFactory(is_pro=True)
            self.artist_1 = self.user_1.create_artist_v2(name='Artist Name')

            self.client.credentials(HTTP_ACCEPT=API_V4_ACCEPT_VALUE)
            self.client.force_authenticate(user=self.user_1)

            self.release = ReleaseFactory(user=self.user_1)
            ReleaseArtistRoleFactory(
                artist=self.artist_1,
                release=self.release,
                role=ReleaseArtistRole.ROLE_PRIMARY_ARTIST,
                main_primary_artist=True,
            )
            self.song = SongFactory(release=self.release)

            self.royalty_split_1 = RoyaltySplitFactory(
                user=self.user_1,
                song=self.song,
                rate=0.5,
                start_date=None,
                end_date=None,
                status=RoyaltySplit.STATUS_CONFIRMED,
                revision=1,
            )
            self.royalty_split_2 = RoyaltySplitFactory(
                user=None,
                song=self.song,
                rate=0.5,
                start_date=None,
                end_date=None,
                status=RoyaltySplit.STATUS_PENDING,
                revision=1,
            )
            RoyaltyInvitationFactory(
                inviter=self.user_1, royalty_split=self.royalty_split_2
            )
            invite = {
                'name': 'Artist Name',
                'email': 'artist@example.com',
                'phone_number': '+46723345678',
            }
            self.payload = [
                {'user_id': self.user_1.id, 'rate': 0.5},
                {'user_id': self.user_2.id, 'rate': 0.4},
                {'invite': invite, 'rate': 0.1},
            ]

    @responses.activate
    @patch("users.helpers.cioevents")
    def test_update_royalty_splits_create_new_pending_ones_and_deletes_old_ones(
        self, mocked_cioevents
    ):
        url = reverse('update-royalty-splits', args=(self.song.id,))

        with freeze_time("2020-01-15"):
            response = self.client.put(url, self.payload, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        self.assertEqual(2, mocked_cioevents.call_count)

        self.assertEqual(len(response.data), 3)
        expected_response_keys = ['name', 'photo', 'rate']
        self.assertEqual(list(response.data[0].keys()), expected_response_keys)
        self.assertEqual(response.data, get_serialized_royalty_splits(self.song))

        old_royalty_splits_ids = [self.royalty_split_1.id, self.royalty_split_2.id]

        new_royalty_splits = RoyaltySplit.objects.filter(song=self.song).exclude(
            id__in=old_royalty_splits_ids
        )

        self.assertEqual(
            new_royalty_splits.get(user=self.user_1).status,
            RoyaltySplit.STATUS_CONFIRMED,
        )
        self.assertEqual(
            new_royalty_splits.get(user=self.user_2).status, RoyaltySplit.STATUS_PENDING
        )
        self.assertEqual(
            new_royalty_splits.get(user=None).status, RoyaltySplit.STATUS_PENDING
        )

        # TODO This creates a state with 1st revision splits that has start_date
        # where it should be None if they get activated
        for split in new_royalty_splits:
            self.assertEqual(split.start_date, date(2020, 1, 15))
            self.assertEqual(split.revision, 1)

        old_royalty_splits = RoyaltySplit.objects.filter(id__in=old_royalty_splits_ids)
        self.assertEqual(old_royalty_splits.count(), 0)

    @responses.activate
    @patch("users.helpers.cioevents")
    def test_update_royalty_splits_allowed_for_admin_role(self, mocked_cioevents):
        with freeze_time("2020-01-15"):
            user = UserFactory(is_pro=True)
            UserArtistRole.objects.create(
                user=user, artist=self.artist_1, type=UserArtistRole.ADMIN
            )
            self.client.force_authenticate(user=user)
            url = reverse('update-royalty-splits', args=(self.song.id,))

            response = self.client.put(url, self.payload, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)

    @responses.activate
    @patch("users.helpers.cioevents")
    def test_update_royalty_splits_not_allowed_for_member_role(self, mocked_cioevents):
        with freeze_time("2020-01-15"):
            user = UserFactory(is_pro=True)
            UserArtistRole.objects.create(
                user=user, artist=self.artist_1, type=UserArtistRole.MEMBER
            )
            self.client.force_authenticate(user=user)
            url = reverse('update-royalty-splits', args=(self.song.id,))

            response = self.client.put(url, self.payload, format='json')

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    @responses.activate
    @patch("users.helpers.cioevents")
    def test_update_royalty_splits_allowed_with_only_email(self, mocked_cioevents):
        url = reverse('update-royalty-splits', args=(self.song.id,))
        self.payload[2]["invite"]["phone_number"] = None

        response = self.client.put(url, self.payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    @responses.activate
    @patch("users.helpers.cioevents")
    def test_update_royalty_splits_allowed_with_only_phone(self, mocked_cioevents):
        url = reverse('update-royalty-splits', args=(self.song.id,))
        self.payload[2]["invite"]["email"] = None

        response = self.client.put(url, self.payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    @responses.activate
    @patch("users.helpers.cioevents")
    def test_update_royalty_splits_not_allowed_without_phone_and_email(
        self, mocked_cioevents
    ):
        url = reverse('update-royalty-splits', args=(self.song.id,))
        self.payload[2]["invite"]["phone_number"] = None
        self.payload[2]["invite"]["email"] = None

        response = self.client.put(url, self.payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    @responses.activate
    @patch("users.helpers.cioevents")
    def test_update_royalty_splits_create_new_pending_ones_and_keeps_old_ones_as_active(
        self, mocked_cioevents
    ):
        url = reverse('update-royalty-splits', args=(self.song.id,))
        self.royalty_split_2.user = self.user_2
        self.royalty_split_2.save()
        old_royalty_splits_ids = [self.royalty_split_1.id, self.royalty_split_2.id]

        RoyaltySplit.objects.filter(id__in=old_royalty_splits_ids).update(
            status=RoyaltySplit.STATUS_ACTIVE
        )

        with freeze_time("2020-01-15"):
            response = self.client.put(url, self.payload, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        self.assertEqual(2, mocked_cioevents.call_count)

        self.assertEqual(len(response.data), 5)

        new_royalty_splits = RoyaltySplit.objects.filter(song=self.song).exclude(
            id__in=old_royalty_splits_ids
        )

        self.assertEqual(
            new_royalty_splits.get(user=self.user_1).status,
            RoyaltySplit.STATUS_CONFIRMED,
        )
        self.assertEqual(
            new_royalty_splits.get(user=self.user_2).status, RoyaltySplit.STATUS_PENDING
        )
        self.assertEqual(
            new_royalty_splits.get(user=None).status, RoyaltySplit.STATUS_PENDING
        )

        for split in new_royalty_splits:
            self.assertEqual(split.start_date, date(2020, 1, 15))
            self.assertEqual(split.revision, 2)

        old_royalty_splits = RoyaltySplit.objects.filter(id__in=old_royalty_splits_ids)
        for royalty_split in old_royalty_splits:
            self.assertEqual(royalty_split.status, RoyaltySplit.STATUS_ACTIVE)
            self.assertEqual(royalty_split.end_date, None)
            self.assertEqual(royalty_split.revision, 1)

    def test_update_royalty_splits_with_unsupported_api_version_returns_error(self):
        url = reverse('update-royalty-splits', args=(self.song.id,))
        self.client.credentials(HTTP_ACCEPT=API_V2_ACCEPT_VALUE)
        response = self.client.put(url, self.payload, format='json')
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        self.assertEqual(response.json(), {'detail': 'API version is not supported.'})

    def test_update_royalty_splits_return_forbidden_error_when_user_is_not_song_owner(
        self,
    ):
        url = reverse('update-royalty-splits', args=(self.song.id,))
        self.client.force_authenticate(user=self.user_2)
        response = self.client.put(url, self.payload, format='json')
        assert response.status_code == status.HTTP_403_FORBIDDEN

        expected_error_message = {
            'detail': 'You need to be owner of the song to have access.'
        }
        self.assertEqual(response.json(), expected_error_message)

    def test_update_not_allowed_for_locked_split(self):
        self.royalty_split_1.is_locked = True
        self.royalty_split_1.save()
        url = reverse('update-royalty-splits', args=(self.song.id,))

        response = self.client.put(url, self.payload, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.json()[0], 'Cannot update locked split')
