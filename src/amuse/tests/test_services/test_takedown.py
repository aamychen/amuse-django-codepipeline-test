from unittest.mock import patch

from django.test import TestCase

from amuse.models.release_takedown_request import ReleaseTakedownRequest
from amuse.services.takedown import Takedown, TakedownResponse
from releases.models import Release
from releases.tests.factories import (
    ReleaseFactory,
    ReleaseArtistRoleFactory,
    SongFactory,
    RoyaltySplitFactory,
    StoreFactory,
    FugaStoreFactory,
    ReleaseStoreDeliveryStatusFactory,
    FugaMetadataFactory,
)
from releases.tests.test_release_model import ReleaseTestCase
from users.tests.factories import UserFactory


class TakedownTestCase(TestCase):
    @patch('amuse.tasks.zendesk_create_or_update_user')
    def setUp(self, mock_zendesk):
        super().setUp()
        self.user = UserFactory()
        self.artist = self.user.create_artist_v2('Le test artiste')
        self.release = ReleaseFactory(user=self.user, status=Release.STATUS_DELIVERED)
        self.release_artist_role = ReleaseArtistRoleFactory(
            artist=self.artist, release=self.release
        )
        self.song = SongFactory(release=self.release)
        self.royalty_split = RoyaltySplitFactory(song=self.song, user=self.release.user)
        self.direct_store = StoreFactory(
            active=True, name='Spotify', internal_name='spotify', admin_active=True
        )
        self.fuga_store = FugaStoreFactory(name='Deezer')
        ReleaseStoreDeliveryStatusFactory(release=self.release, store=self.direct_store)
        ReleaseStoreDeliveryStatusFactory(
            release=self.release, fuga_store=self.fuga_store
        )
        self.fuga_release = FugaMetadataFactory(release=self.release)

    @patch(
        'releases.models.release.get_release_with_license_info',
        return_value=ReleaseTestCase.RELEASE_WITHOUT_LICENSE_INFO,
    )
    @patch.object(Takedown, 'perform_takedown', return_value=None)
    def test_trigger_successful_takedown(self, mock_perform_takedown, mock_response):
        result = Takedown(
            self.release, self.user, ReleaseTakedownRequest.REASON_SWITCH_DISTRIBUTOR
        ).trigger()
        self.assertTrue(result.success)
        mock_perform_takedown.assert_called_once()
        mock_response.assert_called_once()
        assert ReleaseTakedownRequest.objects.filter(
            release=self.release,
            requested_by=self.user,
            takedown_reason=ReleaseTakedownRequest.REASON_SWITCH_DISTRIBUTOR,
        ).exists()

    @patch.object(Takedown, 'perform_takedown', return_value=None)
    def test_trigger_can_only_takedown_delivered_releases(self, mock_perform_takedown):
        self.release.status = Release.STATUS_TAKEDOWN
        self.release.save()

        result = Takedown(
            self.release, self.user, ReleaseTakedownRequest.REASON_SWITCH_DISTRIBUTOR
        ).trigger()

        self.assertFalse(result.success)
        self.assertEqual(result.failure_reason, TakedownResponse.FAILED_REASON_NOT_LIVE)
        mock_perform_takedown.assert_not_called()
        assert not ReleaseTakedownRequest.objects.filter(release=self.release).exists()

        self.release.status = Release.STATUS_SUBMITTED
        self.release.save()

        result = Takedown(
            self.release, self.user, ReleaseTakedownRequest.REASON_SWITCH_DISTRIBUTOR
        ).trigger()

        self.assertFalse(result.success)
        self.assertEqual(result.failure_reason, TakedownResponse.FAILED_REASON_NOT_LIVE)
        mock_perform_takedown.assert_not_called()
        assert not ReleaseTakedownRequest.objects.filter(release=self.release).exists()

        self.release.status = Release.STATUS_NOT_APPROVED
        self.release.save()

        result = Takedown(
            self.release, self.user, ReleaseTakedownRequest.REASON_SWITCH_DISTRIBUTOR
        ).trigger()

        self.assertFalse(result.success)
        self.assertEqual(result.failure_reason, TakedownResponse.FAILED_REASON_NOT_LIVE)
        mock_perform_takedown.assert_not_called()
        assert not ReleaseTakedownRequest.objects.filter(release=self.release).exists()

    @patch.object(Takedown, 'perform_takedown', return_value=None)
    def test_trigger_user_with_advance_cannot_takedown_release(
        self, mock_perform_takedown
    ):
        self.royalty_split.is_locked = True
        self.royalty_split.save()

        result = Takedown(
            self.release, self.user, ReleaseTakedownRequest.REASON_SWITCH_DISTRIBUTOR
        ).trigger()
        self.assertFalse(result.success)
        self.assertEqual(
            result.failure_reason, TakedownResponse.FAILED_REASON_LOCKED_SPLITS
        )
        mock_perform_takedown.assert_not_called()
        assert not ReleaseTakedownRequest.objects.filter(release=self.release).exists()

    @patch(
        'releases.models.release.get_release_with_license_info',
        return_value=ReleaseTestCase.RELEASE_WITH_LICENSE_INFO,
    )
    @patch.object(Takedown, 'perform_takedown', return_value=None)
    def test_trigger_cannot_takedown_release_with_licensed_tracks(
        self, mock_perform_takedown, mock_response
    ):
        result = Takedown(
            self.release, self.user, ReleaseTakedownRequest.REASON_SWITCH_DISTRIBUTOR
        ).trigger()

        self.assertFalse(result.success)
        self.assertEqual(
            result.failure_reason, TakedownResponse.FAILED_REASON_LICENSED_TRACKS
        )
        mock_perform_takedown.assert_not_called()
        mock_response.assert_called_once()
        assert not ReleaseTakedownRequest.objects.filter(release=self.release).exists()

    @patch.object(Takedown, 'perform_takedown', return_value=None)
    def test_trigger_takedown_in_progress(self, mock_perform_takedown):
        takedown = Takedown(
            self.release, self.user, ReleaseTakedownRequest.REASON_OTHER
        )
        takedown._create_takedown_in_progress_cache()

        result = takedown.trigger()
        self.assertFalse(result.success)
        self.assertEqual(
            result.failure_reason, TakedownResponse.FAILED_REASON_TAKEDOWN_IN_PROGRESS
        )
        mock_perform_takedown.assert_not_called()

    @patch("amuse.vendor.fuga.fuga_api.FugaAPIClient.delete_product")
    @patch('amuse.services.takedown.deliver_batches')
    def test_perform_takedown_calls_deliver_batches_with_takedown_args(
        self, mock_deliver, mock_fuga_delete
    ):
        takedown = Takedown(
            self.release, self.user, ReleaseTakedownRequest.REASON_OTHER
        )
        takedown.perform_takedown()
        mock_deliver.assert_called_once_with(
            releases=[self.release],
            delivery_type='takedown',
            user=self.user,
            stores=[self.direct_store.internal_name],
        )
        mock_fuga_delete.assert_called_once_with(
            fuga_product_id=self.fuga_release.product_id
        )
