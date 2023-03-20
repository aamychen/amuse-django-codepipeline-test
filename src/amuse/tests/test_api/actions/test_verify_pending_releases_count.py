from datetime import timedelta
from unittest import mock

from django.utils import timezone
from rest_framework.exceptions import PermissionDenied

from amuse.api.actions.release import VerifyPendingReleasesCount
from amuse.tests.test_api.base import AmuseAPITestCase
from releases.models import Release
from releases.tests.factories import ReleaseFactory
from subscriptions.tests.factories import SubscriptionFactory
from users.tests.factories import UserFactory


class VerifyPendingReleasesCountTestCase(AmuseAPITestCase):
    @mock.patch('amuse.tasks.zendesk_create_or_update_user')
    def setUp(self, mocked_zendesk):
        self.user = UserFactory()

    def test_verify_free_user(self):
        # step 1: everything ok
        VerifyPendingReleasesCount.verify(self.user)

        # step 2: user creates release
        self.release = ReleaseFactory(
            user=self.user, created_by=self.user, status=Release.STATUS_PENDING
        )

        # step 3: exception raised
        with self.assertRaisesMessage(
            PermissionDenied, 'Free user can only have one PENDING release'
        ):
            VerifyPendingReleasesCount.verify(self.user)

    def test_verify_free_trial_user(self):
        sub = SubscriptionFactory(
            user=self.user,
            free_trial_from=timezone.now() - timedelta(days=5),
            free_trial_until=timezone.now() + timedelta(days=5),
        )

        # step 1: everything ok
        VerifyPendingReleasesCount.verify(self.user)

        # step 2: user creates release
        self.release = ReleaseFactory(
            user=self.user, created_by=self.user, status=Release.STATUS_PENDING
        )

        # step 3: exception raised
        with self.assertRaisesMessage(
            PermissionDenied, 'Free Trial user can only have one PENDING release'
        ):
            VerifyPendingReleasesCount.verify(self.user)
