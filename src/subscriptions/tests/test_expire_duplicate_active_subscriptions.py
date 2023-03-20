from unittest.mock import patch

from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from subscriptions.models import Subscription
from subscriptions.tests.factories import SubscriptionFactory


class ExpireDuplicateActiveSubscriptionsTestCase(TestCase):
    @patch('amuse.tasks.zendesk_create_or_update_user')
    def test_command(self, mock_zendesk):
        subscription = SubscriptionFactory()
        subscription2 = SubscriptionFactory(user=subscription.user)
        subscription3 = SubscriptionFactory(user=subscription.user)

        call_command('expire_duplicate_active_subscriptions')
        subscription.refresh_from_db()
        subscription2.refresh_from_db()
        subscription3.refresh_from_db()

        user = subscription.user
        user.refresh_from_db()
        self.assertTrue(subscription.user.is_pro)

        today = timezone.now().date()
        self.assertEqual(subscription.valid_until, today)
        self.assertEqual(subscription.status, Subscription.STATUS_EXPIRED)
        self.assertEqual(subscription2.valid_until, today)
        self.assertEqual(subscription2.status, Subscription.STATUS_EXPIRED)
        self.assertEqual(subscription3.valid_until, None)
        self.assertEqual(subscription3.status, Subscription.STATUS_ACTIVE)
