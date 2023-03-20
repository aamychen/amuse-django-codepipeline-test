import logging

from datetime import datetime
from django.core.cache import cache
from time import time

from amuse.services.delivery.helpers import deliver_batches
from amuse.vendor.fuga.helpers import perform_fuga_delete
from amuse.services.release_delivery_info import ReleaseDeliveryInfo
from amuse.vendor.fuga.fuga_api import FugaAPIClient
from releases.models import Release, FugaMetadata
from users.models import User
from amuse.models.release_takedown_request import ReleaseTakedownRequest

CACHE_PERIOD_IN_SECONDS = 24 * 60 * 60

logger = logging.getLogger(__name__)


class TakedownResponse:
    FAILED_REASON_NOT_LIVE = "not_live"
    FAILED_REASON_TAKEDOWN_IN_PROGRESS = " takedown_in_progress"
    FAILED_REASON_LOCKED_SPLITS = "locked_splits"
    FAILED_REASON_LICENSED_TRACKS = "licensed_tracks"

    def __init__(self, success, error_reason=None):
        self.success = success
        self.failure_reason = error_reason


class Takedown:
    def __init__(self, release, user, takedown_reason):
        self.release = release
        self.user = user
        self.takedown_reason = takedown_reason

    def trigger(self):
        # Can only take down live releases
        if self.release.status not in [
            Release.STATUS_DELIVERED,
            Release.STATUS_RELEASED,
        ]:
            return TakedownResponse(False, TakedownResponse.FAILED_REASON_NOT_LIVE)

        # Cannot take down releases that are in the process of being taken down
        if self._is_takedown_in_progress():
            return TakedownResponse(
                False, TakedownResponse.FAILED_REASON_TAKEDOWN_IN_PROGRESS
            )

        # Check release has no locked splits as this indicates it has an advance
        if self.release.has_locked_splits():
            return TakedownResponse(False, TakedownResponse.FAILED_REASON_LOCKED_SPLITS)

        # Release that contains licensed tracks cannot be taken down.
        if self.release.has_licensed_tracks:
            return TakedownResponse(
                False, TakedownResponse.FAILED_REASON_LICENSED_TRACKS
            )

        logger.info(
            f"Takedown of release ({self.release.id}) triggered by user ({self.user.id})"
        )

        self._create_takedown_request_entry()
        self._create_takedown_in_progress_cache()

        self.perform_takedown()

        return TakedownResponse(True)

    def perform_takedown(self):
        direct_stores = ReleaseDeliveryInfo(self.release).get_direct_delivery_channels(
            'takedown'
        )
        deliver_batches(
            releases=[self.release],
            delivery_type='takedown',
            user=self.user,
            stores=direct_stores,
        )
        fuga_release = FugaMetadata.objects.filter(
            status='PUBLISHED', release=self.release
        ).first()
        if fuga_release:
            perform_fuga_delete(fuga_release)

    def _is_takedown_in_progress(self):
        takedown_json = cache.get(self._generate_takedown_cache_key())
        return takedown_json is not None

    def _generate_takedown_cache_key(self):
        return f"release:{self.release.id}:takedown"

    def _create_takedown_in_progress_cache(self):
        value = {'requested_at': int(time())}
        cache.set(self._generate_takedown_cache_key(), value, CACHE_PERIOD_IN_SECONDS)

    def _create_takedown_request_entry(self):
        takedown_request = ReleaseTakedownRequest(
            release=self.release,
            requested_by=self.user,
            takedown_reason=self.takedown_reason,
        )
        takedown_request.save()
