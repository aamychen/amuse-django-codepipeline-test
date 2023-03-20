import time
import json
from datetime import datetime, timedelta, date

from django.conf import settings
from django.db.models import Q
from amuse.utils import chunks
from amuse.vendor.spotify import SpotifyAPI
from releases.models import Release, Song
from releases.validators import validate_splits_for_songs

from amuse.vendor.segment import events

from amuse.services import smart_link
from amuse.analytics import segment_release_released


def update_delivered():
    releases = Release.objects.filter(
        status=Release.STATUS_DELIVERED, release_date__lte=datetime.today()
    )
    for release in releases:
        release.status = Release.STATUS_RELEASED
        release.save()
        segment_release_released(release)


def update_submitted(to_status=None):
    if to_status is None:
        to_status = Release.STATUS_NOT_APPROVED

    releases = Release.objects.filter(
        status=Release.STATUS_SUBMITTED,
        created__lte=datetime.today() - timedelta(days=1),
    )
    for release in releases:
        release.status = to_status
        release.save()


def splits_integrity_check():
    song_ids = list(
        Song.objects.filter(royalty_splits__isnull=False).values_list("id", flat=True)
    )
    result_dict = validate_splits_for_songs(song_ids)

    return json.dumps(result_dict)


def create_or_update_smart_links_for_releases() -> None:
    """
    Finds Releases that are released today, creates messages for
    all of them and sends them in batches over SNS to amuse-links-django
    service for smart link creation / update.
    """
    releases = Release.objects.filter(
        Q(
            status=Release.STATUS_RELEASED,
            schedule_type=Release.SCHEDULE_TYPE_STATIC,
            release_date=date.today(),
        )
        | Q(
            status=Release.STATUS_RELEASED,
            schedule_type=Release.SCHEDULE_TYPE_ASAP,
            release_date__range=(date.today() - timedelta(days=5), date.today()),
        )
    )
    messages = [
        smart_link.create_release_smart_link_message_payload(release)
        for release in releases
    ]
    for message_batch in chunks(messages, settings.SMART_LINK_MESSAGE_BATCH_SIZE):
        smart_link.send_smart_link_creation_data_to_link_service(message_batch)


def create_smart_links_for_pre_releases() -> None:
    """
    Finds Delivered releases (pre-releases) without smart link,
    creates messages for them and sends those messages in
    batches over SNS to smart link service which handles messages
    and creates smart links for releases.
    """
    releases = Release.objects.filter(
        Q(link=None) | Q(link=''), status=Release.STATUS_DELIVERED
    )
    messages = [
        smart_link.create_pre_release_smart_link_message_payload(release)
        for release in releases
    ]
    for message_batch in chunks(messages, settings.SMART_LINK_MESSAGE_BATCH_SIZE):
        smart_link.send_smart_link_creation_data_to_link_service(message_batch)


def email_smart_links_on_release_day() -> None:
    """
    Queries for releases that have been released
    on current day and have smart links and sends
    smart links via email.

    Sleeps (throttles) for 1.5s for every 100 releases.
    """
    todays_releases = Release.objects.filter(
        link__isnull=False, status=Release.STATUS_RELEASED, release_date=date.today()
    ).exclude(link='')
    for i, release in enumerate(todays_releases, start=1):
        if i % 100 == 0:
            time.sleep(1.5)
        email_smart_link_for_release(release)


def email_smart_link_for_release(release: Release) -> None:
    """
    Emails smart link to owner and creator of the release.
    """
    owner = release.user
    creator = release.created_by

    if creator and owner != creator:
        events.send_smart_link_release_email(creator.id, release.link)

    events.send_smart_link_release_email(owner.id, release.link)
