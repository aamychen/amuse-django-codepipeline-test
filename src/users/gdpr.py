import logging
from uuid import uuid4

import requests
from django.contrib.admin.models import LogEntry
from django.utils import timezone
from django.conf import settings

from amuse import tasks
from amuse.models.minfraud_result import MinfraudResult
from amuse.vendor.adyen import disable_recurring_payment
from amuse.vendor.fuga.fuga_api import FugaAPIClient
from amuse.vendor.zendesk.api import (
    search_zendesk_users_by_email,
    get_zendesk_tickets_by_user,
    delete_ticket,
    permanently_delete_user,
)
from releases.models import RoyaltySplit, Release, FugaMetadata
from subscriptions.models import Subscription
from users.models import ArtistV2, Transaction, TransactionWithdrawal, User
from users.models.user import UserGDPR, UserMetadata

logger = logging.getLogger(__name__)


def launch_gdpr_tasks(user, initiator):
    locked_splits = RoyaltySplit.objects.filter(user=user, is_locked=True)

    if locked_splits:
        return False

    UserGDPR.objects.get_or_create(user=user, defaults={'initiator': initiator})

    delete_user_from_external_services(user)

    tasks.disable_recurring_adyen_payments.delay(user.id)

    tasks.delete_minfraud_entries.delay(user_id=user.id)
    tasks.clean_artist_data.delay(user_id=user.id)
    tasks.delete_artist_v2_history_entries.delay(user_id=user.id)
    tasks.delete_user_history_entries.delay(user_id=user.id)
    tasks.clean_user_data.delay(user_id=user.id)
    tasks.clean_transaction_withdrawals.delay(user_id=user.id)
    tasks.deactivate_user_newsletter_and_active.delay(user_id=user.id)

    UserMetadata.objects.update_or_create(
        user=user, defaults={'gdpr_wiped_at': timezone.now()}
    )

    return True


def delete_user_from_external_services(user):
    tasks.delete_user_from_zendesk.delay(user.id, user.email)
    tasks.delete_user_from_segment.delay(user.id)
    tasks.delete_releases_from_fuga.delay(user.id)


def delete_user_from_zendesk(user_id, user_email):
    # Skip deleting user from zendesk if duplicate accounts registered to the same email
    # This is a workaround caused by us previously treating user emails as case-sensitive
    if (
        User.objects.filter(
            email__iexact=user_email, usermetadata__gdpr_wiped_at=None
        ).count()
        == 1
    ):
        user_search_response = search_zendesk_users_by_email(user_email)

        zendesk_users = user_search_response.json()['users']
        if len(zendesk_users) < 1:
            logger.info(
                f"Did not find any zendesk user matching user: {user_id}, email: {user_email}"
            )
        else:
            zendesk_user_id = zendesk_users[0]['id']

            user_tickets_response = get_zendesk_tickets_by_user(zendesk_user_id)
            for ticket in user_tickets_response.json()['tickets']:
                delete_ticket(ticket['id'])

            permanently_delete_user(zendesk_user_id)

    # Update GDPR table to say user data cleaned
    UserGDPR.objects.filter(user_id=user_id).update(zendesk_data=True)


def delete_user_from_segment(user_id):
    logger.info(f"Attempting to delete user {user_id} from Segment")

    assert settings.SEGMENT_API_TOKEN

    url = 'https://api.segmentapis.com/regulations'

    body = {
        'regulationType': 'SUPPRESS_WITH_DELETE',
        'subjectType': 'USER_ID',
        'subjectIds': [f'{user_id}'],
    }

    headers = {
        'Authorization': f'Bearer {settings.SEGMENT_API_TOKEN}',
        'Content-Type': 'application/json',
    }

    r = requests.post(url, json=body, headers=headers)
    r.raise_for_status()

    # Update GDPR table to say user data cleaned
    UserGDPR.objects.filter(user_id=user_id).update(segment_data=True)


def delete_releases_from_fuga(user_id):
    logger.info(f"Deleting user {user_id} releases from fuga")

    release_ids = list(
        Release.objects.filter(user_id=user_id).values_list("id", flat=True)
    )

    if release_ids:
        fuga_product_ids = FugaMetadata.objects.filter(
            release_id__in=release_ids
        ).values_list("product_id", flat=True)
        fuga_api_client = FugaAPIClient()
        for product_id in fuga_product_ids:
            fuga_api_client.delete_product(product_id)

    UserGDPR.objects.filter(user_id=user_id).update(fuga_data=True)


def disable_recurring_adyen_payments(user_id):
    subscription = Subscription.objects.filter(
        user_id=user_id,
        provider=Subscription.PROVIDER_ADYEN,
        status__in=[Subscription.STATUS_ACTIVE, Subscription.STATUS_GRACE_PERIOD],
    ).first()

    if subscription:
        disable_recurring_payment(subscription)


def delete_minfraud_entries(user_id):
    minfrauds = MinfraudResult.objects.filter(user_id=user_id)
    minfrauds.delete()
    UserGDPR.objects.filter(user_id=user_id).update(minfraud_entries=True)


def delete_artist_v2_history_entries(user_id):
    artist_v2_history = ArtistV2.history.filter(owner_id=user_id)
    artist_v2_history.delete()
    UserGDPR.objects.filter(user_id=user_id).update(artist_v2_history_entries=True)


def clean_transaction_withdrawals(user_id):
    transactions = Transaction.objects.filter(user=user_id)
    for transaction in transactions:
        withdrawals = TransactionWithdrawal.objects.filter(
            transaction_id=transaction.id
        )

        withdrawals.update(name="", address=None, country="", email=None, phone=None)

    UserGDPR.objects.filter(user_id=user_id).update(transaction_withdrawals=True)


def clean_artist_data(user_id):
    user_object = User.objects.filter(id=user_id).first()

    artistv2 = ArtistV2.objects.filter(owner=user_object)

    UserGDPR.objects.filter(user_id=user_id).update(
        artist_v1_names=True, artist_v1_social_links=True
    )

    artistv2.update(
        name="",
        image=None,
        spotify_page=None,
        twitter_name=None,
        facebook_page=None,
        instagram_name=None,
        soundcloud_page=None,
        youtube_channel=None,
        apple_id=None,
        spotify_id=None,
    )

    UserGDPR.objects.filter(user_id=user_id).update(
        artist_v2_names=True, artist_v2_social_links=True
    )


def clean_user_data(user_id):
    User.objects.filter(id=user_id).update(
        first_name="",
        last_name="",
        email=f"{str(uuid4())}@example.com",
        artist_name=None,
        apple_id=None,
        spotify_id=None,
        phone=None,
        country=None,
        language=None,
        facebook_id=None,
        google_id=None,
        profile_link=None,
        profile_photo=None,
        zendesk_id=None,
        spotify_page=None,
        twitter_name=None,
        facebook_page=None,
        instagram_name=None,
        soundcloud_page=None,
        youtube_channel=None,
        apple_signin_id=None,
        firebase_token=None,
    )

    UserGDPR.objects.filter(user_id=user_id).update(
        email_adress=True,
        user_first_name=True,
        user_last_name=True,
        user_social_links=True,
        user_artist_name=True,
        user_apple_signin_id=True,
        user_facebook_id=True,
        user_firebase_token=True,
        user_zendesk_id=True,
    )


def deactivate_user_newsletter_and_active(user_id):
    User.objects.filter(id=user_id).update(newsletter=False, is_active=False)

    UserGDPR.objects.filter(user_id=user_id).update(
        user_newsletter_deactivation=True, user_isactive_deactivation=True
    )


def delete_user_history_entries(user_id):
    user_history_entries = LogEntry.objects.filter(
        content_type_id=55, object_id=user_id
    )

    user_history_entries.delete()
    UserGDPR.objects.filter(user_id=user_id).update(user_history_entries=True)
