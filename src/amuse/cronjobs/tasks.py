import datetime

from django.core.management import call_command

from amuse.celery import app
from amuse.vendor.aws import cloudwatch
from amuse.vendor.fuga import cronjob
from amuse.vendor.spotify import cron
from amuse.vendor.zendesk.cron import backfill_users_missing_zendesk_id
from releases import jobs as release_jobs
from releases import splits_reminders
from releases.models import Release
from subscriptions import helpers as sub_helpers
from users.artistv2_cleanup import delete_orphan_artistv2


@app.task
def delete_orphan_artists():
    delete_orphan_artistv2()


@app.task
def send_splits_remainders():
    splits_reminders.send_split_day_before_release()
    splits_reminders.send_split_not_accepted_3_days()


@app.task
def spotify_backfill_users(limit=50000):
    cron.backfill_eligible_users(limit)


@app.task
def fix_adyen_payment_object():
    call_command('repair_subscription_data', '--fix_payment_methods=true')


@app.task
def deliver_approved_releases(
    limit=5, batchsize=10, delay=5, dryrun=True, user_id=None, days=1, agent_ids=[]
):
    kwargs = {
        'status': 'approved',
        'limit': limit,
        'batchsize': batchsize,
        'delay': delay,
        'user_id': user_id,
        'days': days,
        'agent_ids': agent_ids,
    }
    arg_list = ['trigger_automatic_delivery']

    if dryrun:
        arg_list.append('--dryrun')

    call_command(*arg_list, **kwargs)


@app.task
def deliver_non_delivered_stores(
    limit=5, batchsize=10, delay=5, dryrun=True, user_id=None, days=1
):
    kwargs = {
        'status': 'delivered',
        'limit': limit,
        'batchsize': batchsize,
        'delay': delay,
        'user_id': user_id,
        'days': days,
    }
    arg_list = ['trigger_automatic_delivery']

    if dryrun:
        arg_list.append('--dryrun')

    call_command(*arg_list, **kwargs)


@app.task
def fix_invalid_checksums(limit=10, dryrun=True):
    kwargs = {'limit': limit}
    arg_list = ['fix_checksums']

    if dryrun:
        arg_list.append('--dryrun')

    call_command(*arg_list, **kwargs)


@app.task
def set_unusable_password():
    call_command('setunusableemptypassw')


@app.task
def backfill_vat_for_se_users():
    call_command("vat_sek_backfill")


@app.task
def backfill_vat_for_se_users_with_currency_layer(start_date=None):
    if start_date is None:
        start_date = datetime.date(datetime.date.today().year, 1, 1)
    call_command('vat_sek_backfill_currency_layer', f'--start_date={start_date}')


@app.task
def create_or_update_smart_link():
    release_jobs.create_or_update_smart_links_for_releases()


@app.task
def create_smart_links_for_pre_releases_task():
    release_jobs.create_smart_links_for_pre_releases()


@app.task
def email_smart_links_on_release_day_task():
    release_jobs.email_smart_links_on_release_day()


@app.task
def expire_subscriptions_task():
    """
    Set subscription to EXPIRED if autorenewal is off or payments have failed
    """
    sub_helpers.expire_subscriptions()


@app.task
def renew_adyen_subscriptios():
    """
    Adyen autorenew subscriptions
    """
    sub_helpers.renew_adyen_subscriptions(is_dry_run=False)


@app.task
def renew_apple_subscriptios():
    """
    Apple autorenew subscriptions
    """
    sub_helpers.renew_apple_subscriptions(is_dry_run=False)


@app.task
def update_expired_team_invites():
    call_command("update_expired_team_invitations")


@app.task
def repair_royalty_splits_job():
    call_command("repair_splits", "--fix-type=same_user")


@app.task
def royalty_splits_integrity_check_job():
    release_jobs.splits_integrity_check()


@app.task
def cancel_expired_inactive_splits_job():
    call_command("cancel_expired_inactive_splits")


@app.task
def cancel_pending_royalty_splits_job():
    call_command("cancel_pending_splits")


@app.task
def backfill_zendesk_users_job():
    backfill_users_missing_zendesk_id()


@app.task
def merge_song_writers():
    call_command("merge_writers")


@app.task
def report_double_google_subs():
    call_command("report_duplicate_google_subscriptions")


@app.task
def run_redeliveries(limit=100, batchsize=10, user_id=None):
    kwargs = {'limit': limit, 'batchsize': batchsize, 'user_id': user_id}
    arg_list = ['trigger_redelivery']

    call_command(*arg_list, **kwargs)


@app.task
def cloudwatch_metrics_job():
    cloudwatch.standard_resolution_job()


@app.task
def release_status_cron_job():
    release_jobs.update_delivered()
    release_jobs.update_submitted(to_status=Release.STATUS_INCOMPLETE)


@app.task
def failed_fuga_ingestion_cron_job():
    cronjob.update_ingestion_failed_releases()


@app.task
def parse_fuga_releases():
    cronjob.parse_releases_from_fuga()


@app.task
def parse_fuga_dsp_history_for_releases():
    cronjob.parse_dsp_history_from_fuga()


@app.task
def parse_fuga_dsp_history_for_releases_reversed():
    cronjob.parse_dsp_history_from_fuga(reverse=True)


@app.task
def parse_spotify_data_for_fuga_releases(reverse=None, num_releases=20000):
    cronjob.parse_fuga_releases_from_spotify(reverse=reverse, num_releases=num_releases)


@app.task
def sync_fuga_releases(
    num_releases=100,
    non_synced=None,
    confirm_deleted=None,
    wave=None,
    force_sync=None,
    days=7,
    releases=None,
):
    cronjob.sync_fuga_releases(
        num_releases=num_releases,
        non_synced=non_synced,
        confirm_deleted=confirm_deleted,
        wave=wave,
        force_sync=force_sync,
        days=days,
        releases=releases,
    )


@app.task
def delete_marked_fuga_releases(num_releases=100):
    cronjob.delete_marked_fuga_releases(num_releases=num_releases)


@app.task
def fuga_spotify_direct_deliver(user_id=None, num_releases=100, wave=None):
    cronjob.fuga_spotify_direct_deliver(
        user_id=user_id, num_releases=num_releases, wave=wave
    )


@app.task
def fuga_spotify_takedown(num_releases=100, wave=None):
    cronjob.fuga_spotify_takedown(num_releases=num_releases, wave=wave)


@app.task
def fuga_migration_start(num_releases=100, wave=None):
    cronjob.fuga_migration_start(num_releases=num_releases, wave=wave)


@app.task
def fuga_migration_direct_deliver(num_releases=100, wave=None, user_id=None):
    cronjob.fuga_migration_direct_deliver(
        num_releases=num_releases, wave=wave, user_id=user_id
    )
