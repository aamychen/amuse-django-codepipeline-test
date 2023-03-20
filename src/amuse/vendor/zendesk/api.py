import requests
from django.conf import settings
from requests import HTTPError

from amuse.utils import chunks
from amuse.logging import logger
from subscriptions.models import SubscriptionPlan
from users.models import User


def get_user_payload(user):
    if user.tier == User.TIER_FREE:
        tier = 'free'
    elif user.tier == SubscriptionPlan.TIER_PLUS:
        tier = 'boost'
    elif user.tier == SubscriptionPlan.TIER_PRO:
        tier = 'pro'
    else:
        tier = 'unknown'

    return {
        'name': user.name,
        'email': user.email,
        'external_id': user.id,
        'phone': user.phone,
        'user_fields': {
            'subscription': tier,
            'artist_name': user.artist_name,
            'jarvi5_email': user.email,
            'facebook_scoped': user.profile_link,
            'date_registered': str(user.created),
            'releases': user.releases.count(),
            'fuga_migration': user.fuga_migration,
            'comment': '',
            'user_category': user.get_category_display(),
            'is_frozen': user.is_frozen,
            'is_active': user.is_active,
        },
    }


def create_or_update_user(user_id):
    assert settings.ZENDESK_API_TOKEN

    try:
        user = User.objects.get(pk=user_id)
        payload = {'user': get_user_payload(user)}
        url = '%s/api/v2/users/create_or_update.json' % settings.ZENDESK_API_URL
        auth = ('%s/token' % settings.ZENDESK_API_USER, settings.ZENDESK_API_TOKEN)
        r = requests.post(url, auth=auth, json=payload)
        r.raise_for_status()
        if r.status_code == 201:
            data = r.json()
            if data.get('user') and data.get('user').get('id'):
                user.zendesk_id = data.get('user').get('id')
                user.save()
    except HTTPError as err:
        logger.warning(f'HTTP error occurred while creating zendesk user: {err}')


def update_users(users):
    assert settings.ZENDESK_API_TOKEN

    url = '%s/api/v2/users/update_many.json' % settings.ZENDESK_API_URL
    auth = ('%s/token' % settings.ZENDESK_API_USER, settings.ZENDESK_API_TOKEN)
    user_payloads = [
        get_user_payload(user) for user in users if user and user.zendesk_id
    ]

    # A limit set by zendesk:
    # https://developerblog.zendesk.com/from-100-requests-to-1-introducing-our-new-bulk-and-batch-apis-a5bb294e2132#25d2
    for users_chunk in chunks(user_payloads, 100):
        return requests.put(url, auth=auth, json={'users': users_chunk})


def bulk_create_users(users):
    assert settings.ZENDESK_API_TOKEN

    url = '%s/api/v2/users/create_or_update_many.json' % settings.ZENDESK_API_URL
    auth = ('%s/token' % settings.ZENDESK_API_USER, settings.ZENDESK_API_TOKEN)
    user_payloads = [get_user_payload(user) for user in users]

    return requests.post(url, auth=auth, json={'users': user_payloads})


def show_job_status(job_id):
    assert settings.ZENDESK_API_TOKEN

    url = '%s/api/v2/job_statuses/%s.json' % (settings.ZENDESK_API_URL, job_id)
    auth = ('%s/token' % settings.ZENDESK_API_USER, settings.ZENDESK_API_TOKEN)

    return requests.get(url, auth=auth)


def create_tickets(tickets):
    assert settings.ZENDESK_API_TOKEN

    url = '%s/api/v2/tickets/create_many' % settings.ZENDESK_API_URL
    auth = ('%s/token' % settings.ZENDESK_API_USER, settings.ZENDESK_API_TOKEN)
    for ticket_chunk in chunks(tickets, 100):
        return requests.post(url, auth=auth, json={'tickets': ticket_chunk})


def create_ticket(user_id, data):
    assert settings.ZENDESK_API_TOKEN

    try:
        url = '%s/api/v2/tickets' % settings.ZENDESK_API_URL
        auth = ('%s/token' % settings.ZENDESK_API_USER, settings.ZENDESK_API_TOKEN)

        payload = {
            "ticket": {
                "subject": data.get("subject"),
                "comment": {"body": data.get("comment"), "public": False},
                "type": data.get("type"),
            }
        }

        logger.info(f"Creating Zendesk ticket with following payload: {payload}")

        r = requests.post(url, auth=auth, json=payload)
        r.raise_for_status()
        return r
    except HTTPError as err:
        logger.warning(
            f'HTTP error occurred while creating zendesk ticket. User_id {user_id}: {err}'
        )


def search_zendesk_users_by_email(email):
    assert settings.ZENDESK_API_TOKEN

    url = f'{settings.ZENDESK_API_URL}/api/v2/users/search.json?query=email:"{email}"'
    auth = ('%s/token' % settings.ZENDESK_API_USER, settings.ZENDESK_API_TOKEN)

    r = requests.get(url, auth=auth)
    r.raise_for_status()
    return r


def get_zendesk_tickets_by_user(zendesk_user_id):
    assert settings.ZENDESK_API_TOKEN

    url = f'{settings.ZENDESK_API_URL}/api/v2/users/{zendesk_user_id}/tickets/requested'
    auth = ('%s/token' % settings.ZENDESK_API_USER, settings.ZENDESK_API_TOKEN)

    r = requests.get(url, auth=auth)
    r.raise_for_status()
    return r


def permanently_delete_user(zendesk_user_id):
    assert settings.ZENDESK_API_TOKEN

    url = f"{settings.ZENDESK_API_URL}/api/v2/users/{zendesk_user_id}"
    auth = ('%s/token' % settings.ZENDESK_API_USER, settings.ZENDESK_API_TOKEN)

    logger.info(f"Attempting to delete zendesk user {zendesk_user_id} from Zendesk")

    r = requests.delete(url, auth=auth)
    r.raise_for_status()

    url = f"{settings.ZENDESK_API_URL}/api/v2/deleted_users/{zendesk_user_id}"
    r = requests.delete(url, auth=auth)
    r.raise_for_status()

    return r


def delete_ticket(ticket_id):
    assert settings.ZENDESK_API_TOKEN

    url = f"{settings.ZENDESK_API_URL}/api/v2/tickets/{ticket_id}"
    auth = ('%s/token' % settings.ZENDESK_API_USER, settings.ZENDESK_API_TOKEN)

    logger.info(f"Attempting to delete zendesk ticket:{ticket_id} from Zendesk")

    r = requests.delete(url, auth=auth)
    r.raise_for_status()
    return r
