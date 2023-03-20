from unittest.mock import patch

from django.core.management import call_command
from django.test import TestCase, override_settings

from subscriptions.models import Subscription
from subscriptions.tests.factories import SubscriptionFactory
from users.tests.factories import UserFactory


class ReportDuplicateGoogleSubscriptionsTestCase(TestCase):
    @patch('amuse.tasks.zendesk_create_or_update_user')
    def setUp(self, _):
        self.user = UserFactory()

        self.subscription1 = SubscriptionFactory(
            user=self.user,
            provider=Subscription.PROVIDER_GOOGLE,
            status=Subscription.STATUS_ACTIVE,
        )
        self.subscription2 = SubscriptionFactory(
            user=self.user,
            provider=Subscription.PROVIDER_GOOGLE,
            status=Subscription.STATUS_ACTIVE,
        )

    @override_settings(REPORT_DUPLICATE_GOOGLE_SUBSCRIPTIONS_TO="a@a.com")
    @patch(
        'amuse.vendor.customerio.events.CustomerIOEvents.report_duplicate_google_subscriptions'
    )
    def test_execute_command_successfully(self, mock_cio):
        call_command('report_duplicate_google_subscriptions')
        self.assertEqual(1, mock_cio.call_count)
        mock_cio.assert_called_with(
            recipient='a@a.com',
            data={
                'subscriptions': [
                    {
                        'user_id': self.user.id,
                        'subscription_id': sub.id,
                        'created': str(sub.created),
                    }
                    for sub in [self.subscription1, self.subscription2]
                ]
            },
        )

    @override_settings(REPORT_DUPLICATE_GOOGLE_SUBSCRIPTIONS_TO=None)
    @patch(
        'amuse.vendor.customerio.events.CustomerIOEvents.report_duplicate_google_subscriptions'
    )
    def test_stop_execution_if_receiver_missing(self, mock_cio):
        call_command('report_duplicate_google_subscriptions')
        self.assertEqual(0, mock_cio.call_count)

    @override_settings(REPORT_DUPLICATE_GOOGLE_SUBSCRIPTIONS_TO='')
    @patch(
        'amuse.vendor.customerio.events.CustomerIOEvents.report_duplicate_google_subscriptions'
    )
    def test_stop_execution_if_receiver_missing_2(self, mock_cio):
        call_command('report_duplicate_google_subscriptions')
        self.assertEqual(0, mock_cio.call_count)

    @override_settings(REPORT_DUPLICATE_GOOGLE_SUBSCRIPTIONS_TO=None)
    @patch(
        'amuse.vendor.customerio.events.CustomerIOEvents.report_duplicate_google_subscriptions'
    )
    def test_stop_execution_if_no_duplicates(self, mock_cio):
        self.subscription1.status = Subscription.STATUS_EXPIRED
        self.subscription1.save()

        call_command('report_duplicate_google_subscriptions')
        self.assertEqual(0, mock_cio.call_count)
