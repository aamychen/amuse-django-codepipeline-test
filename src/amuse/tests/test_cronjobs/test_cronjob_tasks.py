from unittest.mock import patch
from django.test import TestCase, override_settings
from amuse.cronjobs import tasks
from releases.models import Release


class TestCronJobTasks(TestCase):
    @patch("amuse.cronjobs.tasks.delete_orphan_artistv2")
    def test_delete_orphan_artists_task(self, mock_fnc):
        tasks.delete_orphan_artists()
        mock_fnc.assert_called_once()

    @patch('releases.splits_reminders.send_split_day_before_release')
    @patch('releases.splits_reminders.send_split_not_accepted_3_days')
    def test_split_reminders(self, mock_after_3_day, mock_day_before_release):
        tasks.send_splits_remainders()
        mock_after_3_day.assert_called_once()
        mock_day_before_release.assert_called_once()

    @patch('amuse.vendor.spotify.cron.backfill_eligible_users')
    def test_spotify_backfill_users(self, mock_fnc):
        tasks.spotify_backfill_users()
        mock_fnc.assert_called_once()

    @patch('amuse.cronjobs.tasks.call_command')
    def test_spotify_backfill_users(self, mock_fnc):
        tasks.fix_adyen_payment_object()
        mock_fnc.assert_called_once_with(
            'repair_subscription_data', '--fix_payment_methods=true'
        )

    @patch('amuse.cronjobs.tasks.call_command')
    def test_deliver_approved_releases(self, mock_fnc):
        tasks.deliver_approved_releases()
        kwargs = {
            'status': 'approved',
            'limit': 5,
            'batchsize': 10,
            'delay': 5,
            'user_id': None,
            'days': 1,
            'agent_ids': [],
        }
        mock_fnc.assert_called_once_with(
            'trigger_automatic_delivery', '--dryrun', **kwargs
        )

    @patch('amuse.cronjobs.tasks.call_command')
    def test_deliver_non_delivered_stores(self, mock_fnc):
        tasks.deliver_non_delivered_stores()
        kwargs = {
            'status': 'delivered',
            'limit': 5,
            'batchsize': 10,
            'delay': 5,
            'user_id': None,
            'days': 1,
        }
        mock_fnc.assert_called_once_with(
            'trigger_automatic_delivery', '--dryrun', **kwargs
        )

    @patch('amuse.cronjobs.tasks.call_command')
    def test_fix_invalid_checksums(self, mock_fnc):
        tasks.fix_invalid_checksums()
        kwargs = {'limit': 10}
        mock_fnc.assert_called_once_with('fix_checksums', '--dryrun', **kwargs)

    @patch('amuse.cronjobs.tasks.call_command')
    def test_set_unusable_password(self, mock_fnc):
        tasks.set_unusable_password()
        mock_fnc.assert_called_once_with('setunusableemptypassw')

    @patch('amuse.cronjobs.tasks.call_command')
    def test_backfill_vat_for_se_users(self, mock_fnc):
        tasks.backfill_vat_for_se_users()
        mock_fnc.assert_called_once_with('vat_sek_backfill')

    @patch('releases.jobs.create_or_update_smart_links_for_releases')
    def test_create_or_update_smart_link(self, mock_fnc):
        tasks.create_or_update_smart_link()
        mock_fnc.assert_called_once()

    @patch('releases.jobs.create_smart_links_for_pre_releases')
    def test_create_smart_links_for_pre_releases_task(self, mock_fnc):
        tasks.create_smart_links_for_pre_releases_task()
        mock_fnc.assert_called_once()

    @patch('releases.jobs.email_smart_links_on_release_day')
    def test_email_smart_links_on_release_day_task(self, mock_fnc):
        tasks.email_smart_links_on_release_day_task()
        mock_fnc.assert_called_once()

    @patch('subscriptions.helpers.expire_subscriptions')
    def test_expire_subscriptions_task(self, mock_fnc):
        tasks.expire_subscriptions_task()
        mock_fnc.assert_called_once()

    @patch('subscriptions.helpers.renew_adyen_subscriptions')
    def test_renew_adyen_subscriptions(self, mock_fnc):
        tasks.renew_adyen_subscriptios()
        mock_fnc.assert_called_once_with(is_dry_run=False)

    @patch('subscriptions.helpers.renew_apple_subscriptions')
    def test_renew_apple_subscriptions(self, mock_fnc):
        tasks.renew_apple_subscriptios()
        mock_fnc.assert_called_once_with(is_dry_run=False)

    @patch('amuse.cronjobs.tasks.call_command')
    def test_update_expired_team_invites(self, mock_fnc):
        tasks.update_expired_team_invites()
        mock_fnc.assert_called_once_with("update_expired_team_invitations")

    @patch('amuse.cronjobs.tasks.call_command')
    def test_repair_royalty_splits_job(self, mock_fnc):
        tasks.repair_royalty_splits_job()
        mock_fnc.assert_called_once_with("repair_splits", "--fix-type=same_user")

    @patch('releases.jobs.splits_integrity_check')
    def test_royalty_splits_integrity_check_jobk(self, mock_fnc):
        tasks.royalty_splits_integrity_check_job()
        mock_fnc.assert_called_once()

    @patch('amuse.cronjobs.tasks.call_command')
    def test_cancel_expired_inactive_splits_job(self, mock_fnc):
        tasks.cancel_expired_inactive_splits_job()
        mock_fnc.assert_called_once_with("cancel_expired_inactive_splits")

    @patch('amuse.cronjobs.tasks.call_command')
    def test_cancel_pending_royalty_splits_job(self, mock_fnc):
        tasks.cancel_pending_royalty_splits_job()
        mock_fnc.assert_called_once_with("cancel_pending_splits")

    @override_settings(ZENDESK_API_TOKEN="xy")
    @patch("amuse.cronjobs.tasks.backfill_users_missing_zendesk_id")
    def test_backfill_zendesk_users_job(self, mock_fnc):
        tasks.backfill_users_missing_zendesk_id()
        mock_fnc.assert_called_once()

    @patch('amuse.cronjobs.tasks.call_command')
    def test_merge_song_writers(self, mock_fnc):
        tasks.merge_song_writers()
        mock_fnc.assert_called_once_with("merge_writers")

    @patch('amuse.cronjobs.tasks.call_command')
    def test_report_double_google_subs(self, mock_fnc):
        tasks.report_double_google_subs()
        mock_fnc.assert_called_once_with("report_duplicate_google_subscriptions")

    @patch('amuse.cronjobs.tasks.call_command')
    def test_run_redeliveries(self, mock_fnc):
        tasks.run_redeliveries()
        mock_fnc.assert_called_once_with(
            "trigger_redelivery", limit=100, batchsize=10, user_id=None
        )

    @patch("amuse.vendor.aws.cloudwatch.standard_resolution_job")
    def test_cloudwatch_metric_job(self, mock_fnc):
        tasks.cloudwatch_metrics_job()
        mock_fnc.assert_called_once()

    @patch('releases.jobs.update_delivered')
    @patch("releases.jobs.update_submitted")
    def test_release_status_cron_job(self, mock_fnc1, mock_fnc2):
        tasks.release_status_cron_job()
        mock_fnc1.assert_called_once_with(to_status=Release.STATUS_INCOMPLETE)
        mock_fnc2.assert_called_once()

    @patch('amuse.vendor.fuga.cronjob.update_ingestion_failed_releases')
    def test_failed_fuga_ingestion_cron_job(self, mock_fnc):
        tasks.failed_fuga_ingestion_cron_job()
        mock_fnc.assert_called_once()
