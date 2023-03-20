import time
from datetime import datetime, timedelta

from django.conf import settings
from requests import HTTPError

from amuse.vendor.zendesk.api import bulk_create_users, show_job_status
from amuse.logging import logger
from users.models import User


def fetch_users_eligible_for_backfill():
    min_created = datetime.now() - timedelta(days=1)
    return User.objects.filter(
        zendesk_id__isnull=True, is_active=True, created__gte=min_created
    ).order_by("-id")[:100]


def fetch_job_results(job_id):
    while True:
        response = show_job_status(job_id)
        response.raise_for_status()

        job_status = response.json()['job_status']
        status = job_status['status']

        if status == 'completed':
            logger.info('Job completed')
            return job_status['results']
        elif status == 'queued':
            logger.info('Job queued, waiting...')
            time.sleep(120)
            continue
        elif status == 'working':
            logger.info('Job in progress, waiting...')
            time.sleep(5)
            continue
        elif status in ['failed', 'killed']:
            logger.info('Job failed')
            message = job_status['message']
            raise Exception(message)
        else:
            raise Exception('Unknown job status returned')


def backfill_zendesk_id(job_results):
    users = []
    for result in job_results:
        try:
            if "error" in result:
                logger.warning(f"Job result error: {result['details']}")
                continue

            user_id = result['external_id']
            zendesk_id = result['id']
            users.append(User(id=user_id, zendesk_id=zendesk_id))
        except Exception as e:
            logger.warning(f"An error occurred: {e}")
    if users is not None:
        User.objects.bulk_update(users, fields=['zendesk_id'])


def backfill_users_missing_zendesk_id():
    assert settings.ZENDESK_API_TOKEN

    try:
        users = fetch_users_eligible_for_backfill()
        if not users.exists():
            logger.info("No users need backfill, exiting")
            return

        logger.info("Bulk updating users on Zendesk")

        response = bulk_create_users(users)
        response.raise_for_status()

        job_status = response.json()["job_status"]
        results = fetch_job_results(job_status['id'])

        backfill_zendesk_id(results)

        logger.info('Users were successfully updated.')
    except HTTPError as http_err:
        logger.error(f'HTTP error occurred: {http_err}')
    except Exception as e:
        logger.exception(f'An error occurred: {e}')
