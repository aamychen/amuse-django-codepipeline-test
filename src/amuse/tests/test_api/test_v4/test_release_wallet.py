from unittest.mock import patch

import responses
from django.urls import reverse

from amuse.tests.helpers import add_zendesk_mock_post_response
from amuse.tests.test_api.base import API_V4_ACCEPT_VALUE, AmuseAPITestCase
from releases.models import RoyaltySplit
from releases.tests.factories import RoyaltySplitFactory
from users.tests.factories import UserFactory
from releases.models import Release
from amuse.api.v4.serializers.release_metadata import ReleaseMetadataSerializer


class SongMetadataViewTestCase(AmuseAPITestCase):
    @responses.activate
    def setUp(self):
        add_zendesk_mock_post_response()
        self.user = UserFactory()
        self.user_no_splits = UserFactory()

        self.split_1 = RoyaltySplitFactory(
            user=self.user, status=RoyaltySplit.STATUS_ACTIVE
        )
        self.split_2 = RoyaltySplitFactory(
            user=self.user, status=RoyaltySplit.STATUS_ACTIVE
        )

        self.client.credentials(HTTP_ACCEPT=API_V4_ACCEPT_VALUE)
        self.url = reverse('releases-wallet-list')

    def test_split_owner_can_access_metadata(self):
        self.client.force_authenticate(self.user)

        response = self.client.get(self.url)
        data = response.json()

        assert response.status_code == 200
        assert len(data) == 2

        sorted_data = sorted(data, key=lambda x: x['id'])
        sorted_releases = sorted(
            [
                (self.split_1.song.release, self.split_1),
                (self.split_2.song.release, self.split_2),
            ],
            key=lambda x: x[0].pk,
        )

        for data, (release, split) in zip(sorted_data, sorted_releases):
            assert data['id'] == release.pk
            assert data['name'] == release.name
            assert 'cover_art' in data
            assert 'main_primary_artist' in data
            assert 'status' in data

            assert len(data['songs']) == 1
            song_data = data['songs'][0]
            assert song_data['id'] == split.song_id
            assert song_data['name'] == split.song.name
            assert song_data['explicit'] == split.song.get_explicit_display()
            assert 'primary_artists' in song_data
            assert data['status'] == 'pending_approval'

    def test_no_splits_user_has_empty_response(self):
        self.client.force_authenticate(self.user_no_splits)

        response = self.client.get(self.url)

        assert response.status_code == 200
        assert len(response.json()) == 0

    def test_unauthenticated_user_cannot_access_metadata(self):
        response = self.client.get(self.url)

        assert response.status_code == 401

    def test_release_status_mapping(self):
        release_1 = self.split_1.song.release
        release_2 = self.split_2.song.release
        release_1.status = Release.STATUS_RELEASED
        release_2.status = Release.STATUS_NOT_APPROVED
        release_1.save()
        release_2.save()

        self.assertEqual(ReleaseMetadataSerializer.get_status(release_1), 'released')
        self.assertEqual(
            ReleaseMetadataSerializer.get_status(release_2), 'not_approved'
        )

        release_1.status = Release.STATUS_TAKEDOWN
        release_1.save()
        self.assertEqual(ReleaseMetadataSerializer.get_status(release_1), 'takedown')
