from datetime import datetime

from unittest.mock import patch
import responses
from django.test import TestCase
from django.utils import timezone

from amuse.models import SupportEvent, SupportRelease
from amuse.support import (
    count_pending_releases,
    assign_pending_releases,
    count_prepared_releases,
    assign_prepared_releases,
)
from amuse.tests.factories import SupportReleaseFactory, SupportEventFactory
from releases.models import Release
from releases.tests.factories import ReleaseFactory, MetadataLanguageFactory
from subscriptions.models import Subscription, SubscriptionPlan
from subscriptions.tests.factories import SubscriptionFactory, SubscriptionPlanFactory
from users.models import User
from users.tests.factories import UserFactory


def create_prepared_release(
    user, created, admin_user, type=Release.TYPE_SINGLE, meta_language=None
):
    release = create_release(user, created, type, meta_language)
    SupportReleaseFactory(assignee=admin_user, release=release, prepared=True)
    SupportEventFactory(user=admin_user, release=release)

    return release


def create_pending_release(
    user, created, admin_user, type=Release.TYPE_SINGLE, meta_language=None
):
    release = create_release(user, created, type, meta_language)
    SupportEventFactory(user=admin_user, release=release)

    return release


def create_release(user, created, type=Release.TYPE_SINGLE, meta_language=None):
    release = ReleaseFactory(
        user=user,
        created_by=user,
        status=Release.STATUS_PENDING,
        type=type,
        meta_language=meta_language,
    )
    created_at = str2dt(created)
    release.created = created_at
    release.save()
    release.refresh_from_db()

    return release


def str2dt(str):
    return datetime.strptime(str, "%Y-%m-%d").replace(tzinfo=None) if str else "None"


def dt2str(date):
    return date.strftime("%Y-%m-%d") if date else "None"


def check_assigned_release(test, release, user, expected=1, prepared=False):
    # test SupportEvent
    assigned_events = list(
        SupportEvent.objects.filter(event=SupportEvent.ASSIGNED, user=user)
    )

    test.assertEqual(
        expected, len(assigned_events), f"Expected {expected} assigned events"
    )
    if expected == 1:
        test.assertEqual(
            release.id,
            assigned_events[0].release_id,
            "Expected assigned event release to match the actual release",
        )

    # test SupportRelease
    assigned_releases = SupportRelease.objects.filter(
        release=release, prepared=prepared
    ).all()
    test.assertEqual(
        expected, len(assigned_releases), f"Expected {expected} assigned releases"
    )

    for assigned_release in assigned_releases:
        test.assertEqual(
            release.id,
            assigned_release.release_id,
            "Expected assigned release to match the actual release",
        )


def check_assigned_releases(test, releases, user, prepared=False):
    assigned_events = list(
        SupportEvent.objects.filter(event=SupportEvent.ASSIGNED, user=user)
    )

    test.assertEqual(
        len(releases), len(assigned_events), f"Expected {len(releases)} assigned events"
    )

    assert set([a.release_id for a in assigned_events]) == set([r.id for r in releases])
    for release in releases:
        assert SupportRelease.objects.filter(
            release=release, prepared=prepared
        ).exists()


class CountPendingReleasesForGraceSubscriptionTestCase(TestCase):
    @responses.activate
    @patch('amuse.tasks.zendesk_create_or_update_user')
    def setUp(self, mock_zendesk):
        self.user = UserFactory()
        self.subscription = SubscriptionFactory(
            user=self.user,
            valid_from=str2dt("2015-07-01"),
            valid_until=str2dt("2015-08-01"),
            grace_period_until=str2dt("2015-08-15"),
            status=Subscription.STATUS_GRACE_PERIOD,
        )

    def test_pro_release_created_after_grace_until(self):
        create_release(self.user, "2015-08-16")

        count = count_pending_releases(tier=SubscriptionPlan.TIER_PRO)
        self.assertEqual(0, count, "Expected 0 pending (pro) releases")

        count = count_pending_releases(tier=User.TIER_FREE)
        self.assertEqual(1, count, "Expected 1 pending (free) releases")

    def test_pro_release_created_before_grace_until(self):
        create_release(self.user, "2015-08-10")

        count = count_pending_releases(tier=SubscriptionPlan.TIER_PRO)
        self.assertEqual(1, count, "Expected 1 pending (pro) releases")

        count = count_pending_releases(tier=User.TIER_FREE)
        self.assertEqual(0, count, "Expected 0 pending (free) releases")

    def test_pro_release_created_before_valid_until(self):
        create_release(self.user, "2015-07-10")

        count = count_pending_releases(tier=SubscriptionPlan.TIER_PRO)
        self.assertEqual(1, count, "Expected 1 pending (pro) releases")

        count = count_pending_releases(tier=User.TIER_FREE)
        self.assertEqual(0, count, "Expected 0 pending (free) releases")

    def test_pro_release_created_before_valid_from(self):
        create_release(self.user, "2015-06-10")

        count = count_pending_releases(tier=SubscriptionPlan.TIER_PRO)
        self.assertEqual(0, count, "Expected 0 pending (pro) releases")

        count = count_pending_releases(tier=User.TIER_FREE)
        self.assertEqual(1, count, "Expected 1 pending (free) releases")

    def test_plus_release_created_before_grace_until(self):
        plan = SubscriptionPlanFactory(tier=SubscriptionPlan.TIER_PLUS)
        self.subscription.plan = plan
        self.subscription.save()
        create_release(self.user, "2015-08-10")

        count = count_pending_releases(tier=SubscriptionPlan.TIER_PRO)
        self.assertEqual(0, count, "Expected 0 pending (pro) releases")

        count = count_pending_releases(tier=SubscriptionPlan.TIER_PLUS)
        self.assertEqual(1, count, "Expected 1 pending (plus) releases")

        count = count_pending_releases(tier=User.TIER_FREE)
        self.assertEqual(0, count, "Expected 0 pending (free) releases")


class CountPendingReleasesForExpiredSubscriptionTestCase(TestCase):
    @responses.activate
    @patch('amuse.tasks.zendesk_create_or_update_user')
    def setUp(self, mock_zendesk):
        self.user = UserFactory()
        self.subscription = SubscriptionFactory(
            user=self.user,
            valid_from=str2dt("2015-07-01"),
            valid_until=str2dt("2015-08-01"),
            status=Subscription.STATUS_EXPIRED,
        )

    def test_release_created_before_valid_from(self):
        create_release(self.user, "2015-06-10")

        count = count_pending_releases(tier=SubscriptionPlan.TIER_PRO)
        self.assertEqual(0, count, "Expected 0 pending (pro) releases")

        count = count_pending_releases(tier=User.TIER_FREE)
        self.assertEqual(1, count, "Expected 1 pending (free) releases")

    def test_release_created_before_valid_until(self):
        create_release(self.user, "2015-07-10")

        count = count_pending_releases(tier=SubscriptionPlan.TIER_PRO)
        self.assertEqual(1, count, "Expected 1 pending (pro) releases")

        count = count_pending_releases(tier=User.TIER_FREE)
        self.assertEqual(0, count, "Expected 0 pending (free) releases")

    def test_release_created_after_valid_until(self):
        create_release(self.user, "2015-10-10")

        count = count_pending_releases(tier=SubscriptionPlan.TIER_PRO)
        self.assertEqual(0, count, "Expected 0 pending (pro) releases")

        count = count_pending_releases(tier=User.TIER_FREE)
        self.assertEqual(1, count, "Expected 1 pending (free) releases")

    def test_plus_release_created_before_valid_until(self):
        plan = SubscriptionPlanFactory(tier=SubscriptionPlan.TIER_PLUS)
        self.subscription.plan = plan
        self.subscription.save()
        create_release(self.user, "2015-07-10")

        count = count_pending_releases(tier=SubscriptionPlan.TIER_PRO)
        self.assertEqual(0, count, "Expected 0 pending (pro) releases")

        count = count_pending_releases(tier=SubscriptionPlan.TIER_PLUS)
        self.assertEqual(1, count, "Expected 1 pending (plus) releases")

        count = count_pending_releases(tier=User.TIER_FREE)
        self.assertEqual(0, count, "Expected 0 pending (free) releases")


class CountPendingReleasesForActiveSubscriptionTestCase(TestCase):
    @responses.activate
    @patch('amuse.tasks.zendesk_create_or_update_user')
    def setUp(self, mock_zendesk):
        self.user = UserFactory()
        self.subscription = SubscriptionFactory(
            user=self.user,
            valid_from=str2dt("2015-07-01"),
            valid_until=str2dt("2015-08-01"),
            status=Subscription.STATUS_ACTIVE,
        )

    def test_release_created_before_valid_from(self):
        create_release(self.user, "2015-06-10")

        count = count_pending_releases(tier=SubscriptionPlan.TIER_PRO)
        self.assertEqual(0, count, "Expected 0 pending (pro) releases")

        count = count_pending_releases(tier=User.TIER_FREE)
        self.assertEqual(1, count, "Expected 1 pending (free) releases")

    def test_release_created_before_valid_until(self):
        create_release(self.user, "2015-07-10")

        count = count_pending_releases(tier=SubscriptionPlan.TIER_PRO)
        self.assertEqual(1, count, "Expected 1 pending (pro) releases")

        count = count_pending_releases(tier=User.TIER_FREE)
        self.assertEqual(0, count, "Expected 0 pending (free) releases")

    def test_release_created_after_valid_until(self):
        create_release(self.user, "2015-10-10")

        count = count_pending_releases(tier=SubscriptionPlan.TIER_PRO)
        self.assertEqual(0, count, "Expected 0 pending (pro) releases")

        count = count_pending_releases(tier=User.TIER_FREE)
        self.assertEqual(1, count, "Expected 1 pending (free) releases")


class AssignPendingReleasesForGraceSubscriptionTestCase(TestCase):
    @responses.activate
    @patch('amuse.tasks.zendesk_create_or_update_user')
    def setUp(self, mock_zendesk):
        self.user = UserFactory()
        self.subscription = SubscriptionFactory(
            user=self.user,
            valid_from=str2dt("2015-07-01"),
            valid_until=str2dt("2015-08-01"),
            grace_period_until=str2dt("2015-08-15"),
            status=Subscription.STATUS_GRACE_PERIOD,
        )

    @responses.activate
    def test_assign_release_created_before_grace_until(self):
        release = create_release(self.user, "2015-08-10")

        count = assign_pending_releases(
            10, self.user, 'created_date', SubscriptionPlan.TIER_PRO
        )
        self.assertEqual(1, count, "Expected 1 assigned pending (pro) releases")

        check_assigned_release(self, release, self.user)

        count = assign_pending_releases(10, self.user, 'created_date', User.TIER_FREE)
        self.assertEqual(0, count, "Expected 0 assigned pending (free) releases")

    @responses.activate
    def test_assign_release_created_before_valid_until(self):
        release = create_release(self.user, "2015-07-10")

        count = assign_pending_releases(
            10, self.user, 'created_date', SubscriptionPlan.TIER_PRO
        )
        self.assertEqual(1, count, "Expected 1 assigned pending (pro) releases")

        check_assigned_release(self, release, self.user)

        count = assign_pending_releases(10, self.user, 'created_date', User.TIER_FREE)
        self.assertEqual(0, count, "Expected 1 assigned pending (free) releases")

    @responses.activate
    def test_assign_plus_release_created_before_valid_until(self):
        plan = SubscriptionPlanFactory(tier=SubscriptionPlan.TIER_PLUS)
        self.subscription.plan = plan
        self.subscription.save()

        release = create_release(self.user, "2015-07-10")

        count = assign_pending_releases(
            10, self.user, 'created_date', SubscriptionPlan.TIER_PLUS
        )
        self.assertEqual(1, count, "Expected 1 assigned pending (pro) releases")

        check_assigned_release(self, release, self.user)

        count = assign_pending_releases(10, self.user, 'created_date', User.TIER_FREE)
        self.assertEqual(0, count, "Expected 0 assigned pending (free) releases")

    @responses.activate
    def test_assign_release_created_before_valid_from(self):
        release = create_release(self.user, "2015-06-10")

        count = assign_pending_releases(
            10, self.user, 'created_date', SubscriptionPlan.TIER_PRO
        )
        self.assertEqual(0, count, "Expected 0 assigned pending (pro) releases")

        check_assigned_release(self, release, self.user, 0)

        count = assign_pending_releases(10, self.user, 'created_date', User.TIER_FREE)
        self.assertEqual(1, count, "Expected 1 assigned pending (free) releases")

        check_assigned_release(self, release, self.user)

    @responses.activate
    def test_assign_plus_release_created_before_valid_from(self):
        plan = SubscriptionPlanFactory(tier=SubscriptionPlan.TIER_PLUS)
        self.subscription.plan = plan
        self.subscription.save()

        release = create_release(self.user, "2015-06-10")

        count = assign_pending_releases(
            10, self.user, 'created_date', SubscriptionPlan.TIER_PLUS
        )
        self.assertEqual(0, count, "Expected 0 assigned pending (pro) releases")

        check_assigned_release(self, release, self.user, 0)

        count = assign_pending_releases(10, self.user, 'created_date', User.TIER_FREE)
        self.assertEqual(1, count, "Expected 1 assigned pending (free) releases")

        check_assigned_release(self, release, self.user)


class AssignPendingReleasesForActiveSubscriptionTestCase(TestCase):
    @responses.activate
    @patch('amuse.tasks.zendesk_create_or_update_user')
    def setUp(self, mock_zendesk):
        self.user = UserFactory()
        SubscriptionFactory(
            user=self.user,
            valid_from=str2dt("2015-07-01"),
            valid_until=str2dt("2015-08-01"),
            status=Subscription.STATUS_ACTIVE,
        )

    @responses.activate
    def test_assign_release_created_after_valid_until(self):
        release = create_release(self.user, "2015-08-10")

        count = assign_pending_releases(
            10, self.user, 'created_date', SubscriptionPlan.TIER_PRO
        )
        self.assertEqual(0, count, "Expected 0 assigned pending (pro) releases")

        check_assigned_release(self, release, self.user, 0)

        count = assign_pending_releases(10, self.user, 'created_date', User.TIER_FREE)
        self.assertEqual(1, count, "Expected 1 assigned pending (free) releases")

        check_assigned_release(self, release, self.user)

    @responses.activate
    def test_assign_release_created_before_valid_until(self):
        release = create_release(self.user, "2015-07-10")

        count = assign_pending_releases(
            10, self.user, 'created_date', SubscriptionPlan.TIER_PRO
        )
        self.assertEqual(1, count, "Expected 1 assigned pending (pro) releases")

        check_assigned_release(self, release, self.user)

        count = assign_pending_releases(10, self.user, 'created_date', User.TIER_FREE)
        self.assertEqual(0, count, "Expected 1 assigned pending (free) releases")

    @responses.activate
    def test_assign_release_created_before_valid_from(self):
        release = create_release(self.user, "2015-06-10")

        count = assign_pending_releases(
            10, self.user, 'created_date', SubscriptionPlan.TIER_PRO
        )
        self.assertEqual(0, count, "Expected 0 assigned pending (pro) releases")

        check_assigned_release(self, release, self.user, 0)

        count = assign_pending_releases(10, self.user, 'created_date', User.TIER_FREE)
        self.assertEqual(1, count, "Expected 1 assigned pending (free) releases")

        check_assigned_release(self, release, self.user)


class AssignPendingReleasesForActiveSubscriptionWithoutValidUntilTestCase(TestCase):
    @responses.activate
    @patch('amuse.tasks.zendesk_create_or_update_user')
    def setUp(self, mock_zendesk):
        self.user = UserFactory()
        SubscriptionFactory(
            user=self.user,
            valid_from=str2dt("2015-07-01"),
            valid_until=None,
            status=Subscription.STATUS_ACTIVE,
        )

    @responses.activate
    def test_assign_release_created_after_valid_from(self):
        release = create_release(self.user, "2015-08-10")

        count = assign_pending_releases(
            10, self.user, 'created_date', SubscriptionPlan.TIER_PRO
        )
        self.assertEqual(1, count, "Expected 1 assigned pending (pro) releases")

        check_assigned_release(self, release, self.user)

        count = assign_pending_releases(10, self.user, 'created_date', User.TIER_FREE)
        self.assertEqual(0, count, "Expected 0 assigned pending (free) releases")

    @responses.activate
    def test_assign_release_created_before_valid_from(self):
        release = create_release(self.user, "2015-06-10")

        count = assign_pending_releases(
            10, self.user, 'created_date', SubscriptionPlan.TIER_PRO
        )
        self.assertEqual(0, count, "Expected 0 assigned pending (pro) releases")

        check_assigned_release(self, release, self.user, 0)

        count = assign_pending_releases(10, self.user, 'created_date', User.TIER_FREE)
        self.assertEqual(1, count, "Expected 1 assigned pending (free) releases")

        check_assigned_release(self, release, self.user)


class AssignPendingReleasesForExpiredSubscriptionTestCase(TestCase):
    @responses.activate
    @patch('amuse.tasks.zendesk_create_or_update_user')
    def setUp(self, mock_zendesk):
        self.user = UserFactory()
        SubscriptionFactory(
            user=self.user,
            valid_from=str2dt("2015-07-01"),
            valid_until=str2dt("2015-08-01"),
            status=Subscription.STATUS_EXPIRED,
        )

    @responses.activate
    def test_assign_release_created_after_valid_until(self):
        release = create_release(self.user, "2015-08-10")

        count = assign_pending_releases(
            10, self.user, 'created_date', SubscriptionPlan.TIER_PRO
        )
        self.assertEqual(0, count, "Expected 0 assigned pending (pro) releases")

        check_assigned_release(self, release, self.user, 0)

        count = assign_pending_releases(10, self.user, 'created_date', User.TIER_FREE)
        self.assertEqual(1, count, "Expected 1 assigned pending (free) releases")

        check_assigned_release(self, release, self.user)

    @responses.activate
    @patch('amuse.support.logger')
    def test_assign_release_tier_mismatch_logs_the_occurrence(self, mock_logger):
        release = create_release(self.user, "2015-08-10")

        with patch('amuse.tasks.zendesk_create_or_update_user'):
            user = UserFactory(is_pro=True)
            subscription = user.subscriptions.first()
            subscription.valid_from = release.created - timezone.timedelta(days=1)
            subscription.save()
            self.assertTrue(user.has_subscription_for_date(release.created))
        release.user = user
        release.save()  # now we have tier = free but release.user.tier = pro

        count = assign_pending_releases(
            10, self.user, 'created_date', SubscriptionPlan.TIER_PRO
        )
        self.assertEqual(0, count, "Expected 0 assigned pending (pro) releases")

        check_assigned_release(self, release, self.user, 0)

        count = assign_pending_releases(10, self.user, 'created_date', User.TIER_FREE)
        self.assertEqual(1, count, "Expected 1 assigned pending (free) releases")

        mock_logger.info.assert_called_with(
            f'Pending free release ({release.id}:pro) was assigned to {self.user.id}'
        )

        check_assigned_release(self, release, self.user)

    @responses.activate
    def test_assign_release_created_before_valid_until(self):
        release = create_release(self.user, "2015-07-10")

        count = assign_pending_releases(
            10, self.user, 'created_date', SubscriptionPlan.TIER_PRO
        )
        self.assertEqual(1, count, "Expected 1 assigned pending (pro) releases")

        check_assigned_release(self, release, self.user)

        count = assign_pending_releases(10, self.user, 'created_date', User.TIER_FREE)
        self.assertEqual(0, count, "Expected 1 assigned pending (free) releases")

    @responses.activate
    def test_assign_release_created_before_valid_from(self):
        release = create_release(self.user, "2015-06-10")

        count = assign_pending_releases(
            10, self.user, 'created_date', SubscriptionPlan.TIER_PRO
        )
        self.assertEqual(0, count, "Expected 0 assigned pending (pro) releases")

        check_assigned_release(self, release, self.user, 0)

        count = assign_pending_releases(10, self.user, 'created_date', User.TIER_FREE)
        self.assertEqual(1, count, "Expected 1 assigned pending (free) releases")

        check_assigned_release(self, release, self.user)


class CountPreparedReleasesForGraceSubscriptionTestCase(TestCase):
    @responses.activate
    @patch('amuse.tasks.zendesk_create_or_update_user')
    def setUp(self, mock_zendesk):
        self.user = UserFactory()
        self.admin = UserFactory()
        self.subscription = SubscriptionFactory(
            user=self.user,
            valid_from=str2dt("2015-07-01"),
            valid_until=str2dt("2015-08-01"),
            grace_period_until=str2dt("2015-08-15"),
            status=Subscription.STATUS_GRACE_PERIOD,
        )

    @patch('amuse.tasks.zendesk_create_or_update_user')
    def test_pro_release_created_after_grace_until(self, mock_zendesk):
        create_prepared_release(self.user, "2015-08-16", self.admin)

        count = count_prepared_releases(tier=SubscriptionPlan.TIER_PRO)
        self.assertEqual(0, count, "Expected 0 prepared (pro) releases")

        count = count_prepared_releases(tier=User.TIER_FREE)
        self.assertEqual(1, count, "Expected 1 prepared (free) releases")

    @patch('amuse.tasks.zendesk_create_or_update_user')
    def test_plus_release_created_after_grace_until(self, mock_zendesk):
        plan = SubscriptionPlanFactory(tier=SubscriptionPlan.TIER_PLUS)
        self.subscription.plan = plan
        self.subscription.save()

        create_prepared_release(self.user, "2015-08-16", self.admin)

        count = count_prepared_releases(tier=SubscriptionPlan.TIER_PLUS)
        self.assertEqual(0, count, "Expected 0 prepared (plus) releases")

        count = count_prepared_releases(tier=User.TIER_FREE)
        self.assertEqual(1, count, "Expected 1 prepared (free) releases")

    @patch('amuse.tasks.zendesk_create_or_update_user')
    def test_pro_release_created_before_grace_until(self, mock_zendesk):
        create_prepared_release(self.user, "2015-08-10", self.admin)

        count = count_prepared_releases(tier=SubscriptionPlan.TIER_PRO)
        self.assertEqual(1, count, "Expected 1 prepared (pro) releases")

        count = count_prepared_releases(tier=User.TIER_FREE)
        self.assertEqual(0, count, "Expected 0 prepared (free) releases")

    @patch('amuse.tasks.zendesk_create_or_update_user')
    def test_plus_release_created_before_grace_until(self, mock_zendesk):
        plan = SubscriptionPlanFactory(tier=SubscriptionPlan.TIER_PLUS)
        self.subscription.plan = plan
        self.subscription.save()

        create_prepared_release(self.user, "2015-08-10", self.admin)

        count = count_prepared_releases(tier=SubscriptionPlan.TIER_PLUS)
        self.assertEqual(1, count, "Expected 1 prepared (plus) releases")

        count = count_prepared_releases(tier=SubscriptionPlan.TIER_PRO)
        self.assertEqual(0, count, "Expected 0 prepared (pro) releases")

        count = count_prepared_releases(tier=User.TIER_FREE)
        self.assertEqual(0, count, "Expected 0 prepared (free) releases")

    @patch('amuse.tasks.zendesk_create_or_update_user')
    def test_pro_release_created_before_valid_until(self, mock_zendesk):
        create_prepared_release(self.user, "2015-07-10", self.admin)

        count = count_prepared_releases(tier=SubscriptionPlan.TIER_PRO)
        self.assertEqual(1, count, "Expected 1 prepared (pro) releases")

        count = count_prepared_releases(tier=User.TIER_FREE)
        self.assertEqual(0, count, "Expected 0 prepared (free) releases")

    @patch('amuse.tasks.zendesk_create_or_update_user')
    def test_pro_release_created_before_valid_from(self, mock_zendesk):
        create_prepared_release(self.user, "2015-06-10", self.admin)

        count = count_prepared_releases(tier=SubscriptionPlan.TIER_PRO)
        self.assertEqual(0, count, "Expected 0 prepared (pro) releases")

        count = count_prepared_releases(tier=User.TIER_FREE)
        self.assertEqual(1, count, "Expected 1 prepared (free) releases")


class CountPreparedReleasesForExpiredSubscriptionTestCase(TestCase):
    @responses.activate
    @patch('amuse.tasks.zendesk_create_or_update_user')
    def setUp(self, mock_zendesk):
        self.user = UserFactory()
        self.admin = UserFactory()
        self.subscription = SubscriptionFactory(
            user=self.user,
            valid_from=str2dt("2015-07-01"),
            valid_until=str2dt("2015-08-01"),
            status=Subscription.STATUS_EXPIRED,
        )

    @patch('amuse.tasks.zendesk_create_or_update_user')
    def test_release_created_before_valid_from(self, mock_zendesk):
        create_prepared_release(self.user, "2015-06-10", self.admin)

        count = count_prepared_releases(tier=SubscriptionPlan.TIER_PRO)
        self.assertEqual(0, count, "Expected 0 prepared (pro) releases")

        count = count_prepared_releases(tier=User.TIER_FREE)
        self.assertEqual(1, count, "Expected 1 prepared (free) releases")

    @patch('amuse.tasks.zendesk_create_or_update_user')
    def test_release_created_before_valid_until(self, mock_zendesk):
        create_prepared_release(self.user, "2015-07-10", self.admin)

        count = count_prepared_releases(tier=SubscriptionPlan.TIER_PRO)
        self.assertEqual(1, count, "Expected 1 prepared (pro) releases")

        count = count_prepared_releases(tier=User.TIER_FREE)
        self.assertEqual(0, count, "Expected 0 prepared (free) releases")

    @patch('amuse.tasks.zendesk_create_or_update_user')
    def test_release_created_after_valid_until(self, mock_zendesk):
        create_prepared_release(self.user, "2015-10-10", self.admin)

        count = count_prepared_releases(tier=SubscriptionPlan.TIER_PRO)
        self.assertEqual(0, count, "Expected 0 prepared (pro) releases")

        count = count_prepared_releases(tier=User.TIER_FREE)
        self.assertEqual(1, count, "Expected 1 prepared (free) releases")


class CountPreparedReleasesForActiveSubscriptionTestCase(TestCase):
    @patch('amuse.tasks.zendesk_create_or_update_user')
    def setUp(self, mock_zendesk):
        self.user = UserFactory()
        self.admin = UserFactory()
        self.subscription = SubscriptionFactory(
            user=self.user,
            valid_from=str2dt("2015-07-01"),
            valid_until=str2dt("2015-08-01"),
            status=Subscription.STATUS_ACTIVE,
        )

    @patch('amuse.tasks.zendesk_create_or_update_user')
    def test_release_created_before_valid_from(self, mock_zendesk):
        create_prepared_release(self.user, "2015-06-10", self.admin)

        count = count_prepared_releases(tier=SubscriptionPlan.TIER_PRO)
        self.assertEqual(0, count, "Expected 0 prepared (pro) releases")

        count = count_prepared_releases(tier=User.TIER_FREE)
        self.assertEqual(1, count, "Expected 1 prepared (free) releases")

    @patch('amuse.tasks.zendesk_create_or_update_user')
    def test_release_created_before_valid_until(self, mock_zendesk):
        create_prepared_release(self.user, "2015-07-10", self.admin)

        count = count_prepared_releases(tier=SubscriptionPlan.TIER_PRO)
        self.assertEqual(1, count, "Expected 1 prepared (pro) releases")

        count = count_prepared_releases(tier=User.TIER_FREE)
        self.assertEqual(0, count, "Expected 0 prepared (free) releases")

    @patch('amuse.tasks.zendesk_create_or_update_user')
    def test_release_created_after_valid_until(self, mock_zendesk):
        create_prepared_release(self.user, "2015-10-10", self.admin)

        count = count_prepared_releases(tier=SubscriptionPlan.TIER_PRO)
        self.assertEqual(0, count, "Expected 0 prepared (pro) releases")

        count = count_prepared_releases(tier=User.TIER_FREE)
        self.assertEqual(1, count, "Expected 1 prepared (free) releases")


class AssignPreparedReleasesForGraceSubscriptionTestCase(TestCase):
    @responses.activate
    @patch('amuse.tasks.zendesk_create_or_update_user')
    def setUp(self, mock_zendesk):
        self.user = UserFactory()
        self.admin = UserFactory()
        self.subscription = SubscriptionFactory(
            user=self.user,
            valid_from=str2dt("2015-07-01"),
            valid_until=str2dt("2015-08-01"),
            grace_period_until=str2dt("2015-08-15"),
            status=Subscription.STATUS_GRACE_PERIOD,
        )

    @responses.activate
    def test_assign_release_created_before_grace_until(self):
        release = create_prepared_release(self.user, "2015-08-10", self.admin)

        count = assign_prepared_releases(
            10, self.user, 'created_date', SubscriptionPlan.TIER_PRO
        )
        self.assertEqual(1, count, "Expected 1 assigned prepared (pro) releases")

        check_assigned_release(self, release, self.user, 1, True)

        count = assign_prepared_releases(10, self.user, 'created_date', User.TIER_FREE)
        self.assertEqual(0, count, "Expected 0 assigned prepared (free) releases")

    @responses.activate
    def test_assign_release_created_before_valid_until(self):
        release = create_prepared_release(self.user, "2015-07-10", self.admin)

        count = assign_prepared_releases(
            10, self.user, 'created_date', SubscriptionPlan.TIER_PRO
        )
        self.assertEqual(1, count, "Expected 1 assigned prepared (pro) releases")

        check_assigned_release(self, release, self.user, 1, True)

        count = assign_prepared_releases(10, self.user, 'created_date', User.TIER_FREE)
        self.assertEqual(0, count, "Expected 1 assigned prepared (free) releases")

    @responses.activate
    def test_assign_plus_release_created_before_valid_until(self):
        plan = SubscriptionPlanFactory(tier=SubscriptionPlan.TIER_PLUS)
        self.subscription.plan = plan
        self.subscription.save()

        release = create_prepared_release(self.user, "2015-07-10", self.admin)

        count = assign_prepared_releases(
            10, self.user, 'created_date', SubscriptionPlan.TIER_PLUS
        )
        self.assertEqual(1, count, "Expected 1 assigned prepared (plus) releases")

        check_assigned_release(self, release, self.user, 1, True)

        count = assign_prepared_releases(10, self.user, 'created_date', User.TIER_FREE)
        self.assertEqual(0, count, "Expected 0 assigned prepared (free) releases")

    @responses.activate
    def test_assign_release_created_before_valid_from(self):
        release = create_prepared_release(self.user, "2015-06-10", self.admin)

        count = assign_prepared_releases(
            10, self.user, 'created_date', SubscriptionPlan.TIER_PRO
        )
        self.assertEqual(0, count, "Expected 0 assigned prepared (pro) releases")

        count = assign_prepared_releases(10, self.user, 'created_date', User.TIER_FREE)
        self.assertEqual(1, count, "Expected 1 assigned prepared (free) releases")

        check_assigned_release(self, release, self.user, 1, True)

    @responses.activate
    def test_assign_plus_release_created_before_valid_from(self):
        plan = SubscriptionPlanFactory(tier=SubscriptionPlan.TIER_PLUS)
        self.subscription.plan = plan
        self.subscription.save()

        release = create_prepared_release(self.user, "2015-06-10", self.admin)

        count = assign_prepared_releases(
            10, self.user, 'created_date', SubscriptionPlan.TIER_PLUS
        )
        self.assertEqual(0, count, "Expected 0 assigned prepared (plus) releases")

        count = assign_prepared_releases(10, self.user, 'created_date', User.TIER_FREE)
        self.assertEqual(1, count, "Expected 1 assigned prepared (free) releases")

        check_assigned_release(self, release, self.user, 1, True)


class AssignPreparedReleasesForActiveSubscriptionTestCase(TestCase):
    @responses.activate
    @patch('amuse.tasks.zendesk_create_or_update_user')
    def setUp(self, mock_zendesk):
        self.user = UserFactory()
        self.admin = UserFactory()
        SubscriptionFactory(
            user=self.user,
            valid_from=str2dt("2015-07-01"),
            valid_until=str2dt("2015-08-01"),
            status=Subscription.STATUS_ACTIVE,
        )

    @responses.activate
    def test_assign_release_created_after_valid_until(self):
        release = create_prepared_release(self.user, "2015-08-10", self.admin)

        count = assign_prepared_releases(
            10, self.user, 'created_date', SubscriptionPlan.TIER_PRO
        )
        self.assertEqual(0, count, "Expected 0 assigned prepared (pro) releases")

        count = assign_prepared_releases(10, self.user, 'created_date', User.TIER_FREE)
        self.assertEqual(1, count, "Expected 1 assigned prepared (free) releases")

        check_assigned_release(self, release, self.user, 1, True)

    @responses.activate
    def test_assign_release_created_before_valid_until(self):
        release = create_prepared_release(self.user, "2015-07-10", self.admin)

        count = assign_prepared_releases(
            10, self.user, 'created_date', SubscriptionPlan.TIER_PRO
        )
        self.assertEqual(1, count, "Expected 1 assigned prepared (pro) releases")

        check_assigned_release(self, release, self.user, 1, True)

        count = assign_prepared_releases(10, self.user, 'created_date', User.TIER_FREE)
        self.assertEqual(0, count, "Expected 1 assigned prepared (free) releases")

    @responses.activate
    def test_assign_release_created_before_valid_from(self):
        release = create_prepared_release(self.user, "2015-06-10", self.admin)

        count = assign_prepared_releases(
            10, self.user, 'created_date', SubscriptionPlan.TIER_PRO
        )
        self.assertEqual(0, count, "Expected 0 assigned prepared (pro) releases")

        count = assign_prepared_releases(10, self.user, 'created_date', User.TIER_FREE)
        self.assertEqual(1, count, "Expected 1 assigned prepared (free) releases")

        check_assigned_release(self, release, self.user, 1, True)


class AssignPreparedReleasesForActiveSubscriptionWithoutValidUntilTestCase(TestCase):
    @responses.activate
    @patch('amuse.tasks.zendesk_create_or_update_user')
    def setUp(self, mock_zendesk):
        self.user = UserFactory()
        self.admin = UserFactory()
        SubscriptionFactory(
            user=self.user,
            valid_from=str2dt("2015-07-01"),
            valid_until=None,
            status=Subscription.STATUS_ACTIVE,
        )

    @responses.activate
    def test_assign_release_created_after_valid_from(self):
        release = create_prepared_release(self.user, "2015-08-10", self.admin)

        count = assign_prepared_releases(
            10, self.user, 'created_date', SubscriptionPlan.TIER_PRO
        )
        self.assertEqual(1, count, "Expected 1 assigned prepared (pro) releases")

        check_assigned_release(self, release, self.user, 1, True)

        count = assign_prepared_releases(10, self.user, 'created_date', User.TIER_FREE)
        self.assertEqual(0, count, "Expected 0 assigned prepared (free) releases")

    @responses.activate
    def test_assign_release_created_before_valid_from(self):
        release = create_prepared_release(self.user, "2015-06-10", self.admin)

        count = assign_prepared_releases(
            10, self.user, 'created_date', SubscriptionPlan.TIER_PRO
        )
        self.assertEqual(0, count, "Expected 0 assigned prepared (pro) releases")

        count = assign_prepared_releases(10, self.user, 'created_date', User.TIER_FREE)
        self.assertEqual(1, count, "Expected 1 assigned prepared (free) releases")

        check_assigned_release(self, release, self.user, 1, True)


class AssignPreparedReleasesForExpiredSubscriptionTestCase(TestCase):
    @responses.activate
    @patch('amuse.tasks.zendesk_create_or_update_user')
    def setUp(self, mock_zendesk):
        self.user = UserFactory()
        self.admin = UserFactory()
        SubscriptionFactory(
            user=self.user,
            valid_from=str2dt("2015-07-01"),
            valid_until=str2dt("2015-08-01"),
            status=Subscription.STATUS_EXPIRED,
        )

    @responses.activate
    def test_assign_release_created_after_valid_until(self):
        release = create_prepared_release(self.user, "2015-08-10", self.admin)

        count = assign_prepared_releases(
            10, self.user, 'created_date', SubscriptionPlan.TIER_PRO
        )
        self.assertEqual(0, count, "Expected 0 assigned prepared (pro) releases")

        count = assign_prepared_releases(10, self.user, 'created_date', User.TIER_FREE)
        self.assertEqual(1, count, "Expected 1 assigned prepared (free) releases")

        check_assigned_release(self, release, self.user, 1, True)

    @responses.activate
    @patch('amuse.support.logger')
    def test_assign_release_tier_mismatch_logs_the_occurence(self, mock_logger):
        release = create_prepared_release(self.user, "2015-08-10", self.admin)

        with patch('amuse.tasks.zendesk_create_or_update_user'):
            user = UserFactory(is_pro=True)
            subscription = user.subscriptions.first()
            subscription.valid_from = release.created - timezone.timedelta(days=1)
            subscription.save()
            self.assertTrue(user.has_subscription_for_date(release.created))
        release.user = user
        release.save()  # now we have tier = free but release.user.tier = pro

        count = assign_prepared_releases(
            10, self.user, 'created_date', SubscriptionPlan.TIER_PRO
        )
        self.assertEqual(0, count, "Expected 0 assigned prepared (pro) releases")

        count = assign_prepared_releases(10, self.user, 'created_date', User.TIER_FREE)
        self.assertEqual(1, count, "Expected 1 assigned prepared (free) releases")

        mock_logger.info.assert_called_with(
            f'Prepared free release ({release.id}:pro) was assigned to {self.user.id}'
        )

        check_assigned_release(self, release, self.user, 1, True)

    @responses.activate
    def test_assign_release_created_before_valid_until(self):
        release = create_prepared_release(self.user, "2015-07-10", self.admin)

        count = assign_prepared_releases(
            10, self.user, 'created_date', SubscriptionPlan.TIER_PRO
        )
        self.assertEqual(1, count, "Expected 1 assigned prepared (pro) releases")

        check_assigned_release(self, release, self.user, 1, True)

        count = assign_prepared_releases(10, self.user, 'created_date', User.TIER_FREE)
        self.assertEqual(0, count, "Expected 1 assigned prepared (free) releases")

    @responses.activate
    def test_assign_release_created_before_valid_from(self):
        release = create_prepared_release(self.user, "2015-06-10", self.admin)

        count = assign_prepared_releases(
            10, self.user, 'created_date', SubscriptionPlan.TIER_PRO
        )
        self.assertEqual(0, count, "Expected 0 assigned prepared (pro) releases")

        count = assign_prepared_releases(10, self.user, 'created_date', User.TIER_FREE)
        self.assertEqual(1, count, "Expected 1 assigned prepared (free) releases")

        check_assigned_release(self, release, self.user, 1, True)


class IgnoresSubscriptionGracePeriodIfValidUntilIsNullTestCase(TestCase):
    @responses.activate
    @patch('amuse.tasks.zendesk_create_or_update_user')
    def setUp(self, mock_zendesk):
        self.user = UserFactory()
        self.admin = UserFactory()
        SubscriptionFactory(
            user=self.user,
            valid_from=str2dt("2020-01-01"),
            valid_until=None,
            grace_period_until=str2dt("2020-02-01"),
            status=Subscription.STATUS_ACTIVE,
        )

    @responses.activate
    def test_count_pending_releases_ignores_grace_period_if_valid_until_is_null(self):
        release = create_pending_release(self.user, "2020-03-01", self.admin)

        count = count_pending_releases(User.TIER_FREE)
        assert count == 0

        count = count_pending_releases(SubscriptionPlan.TIER_PRO)
        assert count == 1

    @responses.activate
    def test_count_prepared_releases_ignores_grace_period_if_valid_until_is_null(self):
        release = create_prepared_release(self.user, "2020-03-01", self.admin)

        count = count_prepared_releases(User.TIER_FREE)
        assert count == 0

        count = count_prepared_releases(SubscriptionPlan.TIER_PRO)
        assert count == 1

    @responses.activate
    def test_assign_pending_releases_ignores_grace_period_if_valid_until_is_null(self):
        release = create_pending_release(self.user, "2020-03-01", self.admin)

        count = assign_pending_releases(10, self.admin, "created_date", User.TIER_FREE)
        assert count == 0

        count = assign_pending_releases(
            10, self.admin, "created_date", SubscriptionPlan.TIER_PRO
        )
        assert count == 1

    @responses.activate
    def test_assign_prepared_releases_ignores_grace_period_if_valid_until_is_null(self):
        release = create_prepared_release(self.user, "2020-03-01", self.admin)

        count = assign_prepared_releases(10, self.admin, "created_date", User.TIER_FREE)
        assert count == 0

        count = assign_prepared_releases(
            10, self.admin, "created_date", SubscriptionPlan.TIER_PRO
        )
        assert count == 1


class RespectsSubscriptionGracePeriodIfValidUntilIsSetTestCase(TestCase):
    @responses.activate
    @patch('amuse.tasks.zendesk_create_or_update_user')
    def setUp(self, mock_zendesk):
        self.user = UserFactory()
        self.admin = UserFactory()
        SubscriptionFactory(
            user=self.user,
            valid_from=str2dt("2020-01-01"),
            valid_until=str2dt("2020-02-01"),
            grace_period_until=str2dt("2020-02-14"),
            status=Subscription.STATUS_ACTIVE,
        )

    @responses.activate
    def test_count_pending_releases_respects_grace_period_if_valid_until_is_set(self):
        release = create_pending_release(self.user, "2020-02-14", self.admin)

        count = count_pending_releases(tier=User.TIER_FREE)
        assert count == 0

        count = count_pending_releases(tier=SubscriptionPlan.TIER_PRO)
        assert count == 1

    @responses.activate
    def test_count_prepared_releases_respects_grace_period_if_valid_until_is_set(self):
        release = create_prepared_release(self.user, "2020-02-14", self.admin)

        count = count_prepared_releases(tier=User.TIER_FREE)
        assert count == 0

        count = count_prepared_releases(tier=SubscriptionPlan.TIER_PRO)
        assert count == 1

    @responses.activate
    def test_assign_pending_releases_respects_grace_period_if_valid_until_is_set(self):
        release = create_pending_release(self.user, "2020-02-14", self.admin)

        count = assign_pending_releases(10, self.admin, "created_date", User.TIER_FREE)
        assert count == 0

        count = assign_pending_releases(
            10, self.admin, "created_date", SubscriptionPlan.TIER_PRO
        )
        assert count == 1

    @responses.activate
    def test_assign_prepared_releases_respects_grace_period_if_valid_until_is_set(self):
        release = create_prepared_release(self.user, "2020-02-14", self.admin)

        count = assign_prepared_releases(10, self.admin, "created_date", User.TIER_FREE)
        assert count == 0

        count = assign_prepared_releases(
            10, self.admin, "created_date", SubscriptionPlan.TIER_PRO
        )
        assert count == 1


class AssignPreparedReleasesWithReleaseTypeFilter(TestCase):
    @responses.activate
    @patch('amuse.tasks.zendesk_create_or_update_user')
    def setUp(self, mock_zendesk):
        self.user = UserFactory()
        self.admin = UserFactory()
        SubscriptionFactory(
            user=self.user,
            valid_from=str2dt("2015-07-01"),
            valid_until=str2dt("2015-08-01"),
            status=Subscription.STATUS_ACTIVE,
        )
        self.album_release = create_prepared_release(
            self.user, "2015-08-10", self.admin, Release.TYPE_ALBUM
        )
        self.ep_release = create_prepared_release(
            self.user, "2015-08-10", self.admin, Release.TYPE_EP
        )
        self.single_release = create_prepared_release(
            self.user, "2015-08-10", self.admin, Release.TYPE_SINGLE
        )

    @responses.activate
    def test_assign_release_single_only(self):
        count = assign_prepared_releases(
            10,
            self.user,
            'created_date',
            User.TIER_FREE,
            release_type=Release.TYPE_SINGLE,
        )

        self.assertEqual(1, count, "Expected 1 assigned prepared releases")
        check_assigned_releases(self, [self.single_release], self.user, True)

    @responses.activate
    def test_assign_release_album_ep_only(self):
        count = assign_prepared_releases(
            10,
            self.user,
            'created_date',
            User.TIER_FREE,
            release_type=Release.TYPE_ALBUM,
        )

        self.assertEqual(2, count, "Expected 2 assigned prepared releases")
        check_assigned_releases(
            self, [self.album_release, self.ep_release], self.user, True
        )


class AssignPreparedReleasesWithLanguageFilter(TestCase):
    @responses.activate
    @patch('amuse.tasks.zendesk_create_or_update_user')
    def setUp(self, mock_zendesk):
        self.user = UserFactory()
        self.admin = UserFactory()
        SubscriptionFactory(
            user=self.user,
            valid_from=str2dt("2015-07-01"),
            valid_until=str2dt("2015-08-01"),
            status=Subscription.STATUS_ACTIVE,
        )
        spanish = MetadataLanguageFactory(
            name='Spanish', fuga_code='es', iso_639_1='es', sort_order=1
        )
        swedish = MetadataLanguageFactory(
            name='Swedish', fuga_code='se', iso_639_1='se', sort_order=2
        )
        self.swedish_release = create_prepared_release(
            self.user, "2015-08-10", self.admin, meta_language=swedish
        )
        self.spanish_release = create_prepared_release(
            self.user, "2015-08-10", self.admin, meta_language=spanish
        )

    @responses.activate
    def test_assign_release_spanish_only(self):
        count = assign_prepared_releases(
            10, self.user, 'created_date', User.TIER_FREE, language="spanish"
        )
        self.assertEqual(1, count, "Expected 1 assigned prepared releases")

        check_assigned_releases(self, [self.spanish_release], self.user, True)

    def test_assign_release_not_spanish(self):
        count = assign_prepared_releases(
            10, self.user, 'created_date', User.TIER_FREE, language="not-spanish"
        )

        self.assertEqual(1, count, "Expected 1 assigned prepared releases")
        check_assigned_releases(self, [self.swedish_release], self.user, True)


class AssignPendingReleasesWithReleaseTypeFilter(TestCase):
    @responses.activate
    @patch('amuse.tasks.zendesk_create_or_update_user')
    def setUp(self, mock_zendesk):
        self.user = UserFactory()
        self.admin = UserFactory()
        SubscriptionFactory(
            user=self.user,
            valid_from=str2dt("2015-07-01"),
            valid_until=str2dt("2015-08-01"),
            status=Subscription.STATUS_ACTIVE,
        )
        self.album_release = create_pending_release(
            self.user, "2015-08-10", self.admin, Release.TYPE_ALBUM
        )
        self.ep_release = create_pending_release(
            self.user, "2015-08-10", self.admin, Release.TYPE_EP
        )
        self.single_release = create_pending_release(
            self.user, "2015-08-10", self.admin, Release.TYPE_SINGLE
        )

    @responses.activate
    def test_assign_release_single_only(self):
        count = assign_pending_releases(
            10,
            self.user,
            'created_date',
            User.TIER_FREE,
            release_type=Release.TYPE_SINGLE,
        )

        self.assertEqual(1, count, "Expected 1 assigned prepared releases")
        check_assigned_releases(self, [self.single_release], self.user)

    @responses.activate
    def test_assign_release_album_ep_only(self):
        count = assign_pending_releases(
            10,
            self.user,
            'created_date',
            User.TIER_FREE,
            release_type=Release.TYPE_ALBUM,
        )

        self.assertEqual(2, count, "Expected 2 assigned prepared releases")
        check_assigned_releases(self, [self.album_release, self.ep_release], self.user)


class AssignPreparedReleasesWithLanguageFilter(TestCase):
    @responses.activate
    @patch('amuse.tasks.zendesk_create_or_update_user')
    def setUp(self, mock_zendesk):
        self.user = UserFactory()
        self.admin = UserFactory()
        SubscriptionFactory(
            user=self.user,
            valid_from=str2dt("2015-07-01"),
            valid_until=str2dt("2015-08-01"),
            status=Subscription.STATUS_ACTIVE,
        )
        spanish = MetadataLanguageFactory(
            name='Spanish', fuga_code='es', iso_639_1='es', sort_order=1
        )
        swedish = MetadataLanguageFactory(
            name='Swedish', fuga_code='se', iso_639_1='se', sort_order=2
        )
        self.swedish_release = create_pending_release(
            self.user, "2015-08-10", self.admin, meta_language=swedish
        )
        self.spanish_release = create_pending_release(
            self.user, "2015-08-10", self.admin, meta_language=spanish
        )

    @responses.activate
    def test_assign_release_spanish_only(self):
        count = assign_pending_releases(
            10, self.user, 'created_date', User.TIER_FREE, language="spanish"
        )
        self.assertEqual(1, count, "Expected 1 assigned prepared releases")

        check_assigned_releases(self, [self.spanish_release], self.user)

    def test_assign_release_not_spanish(self):
        count = assign_pending_releases(
            10, self.user, 'created_date', User.TIER_FREE, language="non-spanish"
        )
        self.assertEqual(1, count, "Expected 1 assigned prepared releases")

        check_assigned_releases(self, [self.swedish_release], self.user)
