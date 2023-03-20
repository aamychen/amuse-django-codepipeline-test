from statistics import stdev

import boto3
from django.contrib.messages import constants
from django.utils.translation import override as translation_override
from django.contrib.admin.models import LogEntry, ADDITION
from django.contrib.contenttypes.models import ContentType
from django.utils.encoding import force_text
from typing import List

from amuse import tasks
from amuse.analytics import (
    segment_release_approved,
    segment_release_not_approved,
    segment_release_rejected,
    segment_release_taken_down,
    segment_release_deleted,
)
from amuse.models.acrcloud import ACRCloudMatch
from amuse.models.event import Event
from amuse.models.support import SupportEvent
from amuse.storages import S3Storage
from contenttollgate.blacklist import find_offending_artist_names
from releases.models import Song
from releases.models import SongArtistRole
from releases.models import Store, Release
from users.models import RoyaltyInvitation, SongArtistInvitation
from users.models import User


def generate_presigned_post(bucket, key):
    storage = S3Storage(bucket_name=bucket)
    session = boto3.session.Session()

    client = session.client(
        service_name='s3',
        aws_access_key_id=storage.access_key,
        aws_secret_access_key=storage.secret_key,
        endpoint_url=storage.endpoint_url,
    )
    return client.generate_presigned_post(Bucket=bucket, Key=key)


def get_users_info_for_release(release):
    users_info = {'owner': _get_user_info(release.user, release)}
    if release.created_by and release.user != release.created_by:
        users_info['creator'] = _get_user_info(release.created_by, release)
    return users_info


def _get_user_info(user, release):
    event = Event.objects.content_object(release).type(type=Event.TYPE_CREATE).first()

    return {
        'model': user,
        'release_counters': {
            'total': user.releases.count,
            'delivered': user.releases.filter(
                status__in=(Release.STATUS_DELIVERED, Release.STATUS_RELEASED)
            ).count(),
        },
        'phone': {
            'number': user.phone,
            'uses': User.objects.filter(phone=user.phone).count(),
            'flagged': User.objects.filter(
                phone=user.phone, category=User.CATEGORY_FLAGGED
            ).exists(),
        },
        'tier': user.tier,
        'display_country': f'{event.get_client_display()}/{event.version or "unknown"}'
        if event
        else 'N/A',
        'category': user.get_category_display(),
        'flagged': user.category == User.CATEGORY_FLAGGED,
    }


def disable_yt_content_id_for_release(release):
    release.songs.update(youtube_content_id=Song.YT_CONTENT_ID_NONE)
    store = Store.get_yt_content_id_store()
    if store in release.stores.all():
        release.stores.remove(store)


def enable_yt_content_id_for_release(release):
    release.songs.update(youtube_content_id=Song.YT_CONTENT_ID_MONETIZE)
    store = Store.get_yt_content_id_store()
    release.stores.add(store)


def get_alert_tag(messages):
    msgs = list(messages)
    alert_tag = ""
    if msgs and msgs[0]:
        level_to_alert_tag = {
            constants.DEBUG: "alert-info",
            constants.INFO: "alert-primary",
            constants.SUCCESS: "alert-success",
            constants.WARNING: "alert-warning",
            constants.ERROR: "alert-danger",
        }
        alert_tag = level_to_alert_tag[msgs[0].level]
    return alert_tag


def calculate_acr_warning_severity(warnings, song_id):
    if warnings and 'acr_cloud_warnings' in warnings:
        for acr_match in warnings['acr_cloud_warnings']:
            if acr_match['show_warning'] and acr_match['track_id'] == song_id:
                return 'critical'
            elif (
                acr_match['show_warning_on_track_level']
                and acr_match['track_id'] == song_id
            ):
                return 'match'
    return None


def show_audio_recognition_warning(song):
    results = ACRCloudMatch.objects.filter(song=song).all()

    if find_offending_artist_names([a.artist_name for a in results]):
        return True

    if len(results) <= 4 and any([r.score >= 97 for r in results]):
        return True

    if len(results) > 1 and stdev([r.offset for r in results]) > 5:
        return True

    primary = song.songartistrole_set.filter(
        role=SongArtistRole.ROLE_PRIMARY_ARTIST
    ).values_list("artist__name", flat=True)

    # Check for matching track with different ISRC
    for result in results:
        if (
            result.artist_name in primary or result.track_title == song.name
        ) and result.match_isrc != song.isrc_code:
            return True

    return False


def get_selected_error_flags(release):
    error_flags = []
    for error_flag_key, is_set in release.error_flags.iteritems():
        if is_set:
            error_flags.append(error_flag_key)
    return error_flags


def send_royalty_invitations(release_id):
    count = RoyaltyInvitation.objects.filter(
        status=RoyaltyInvitation.STATUS_CREATED, royalty_split__song__release=release_id
    ).count()

    if count > 0:
        tasks.send_royalty_invite_email(release_id)


def send_song_artist_invitations(release_id):
    count = SongArtistInvitation.objects.filter(
        status=SongArtistInvitation.STATUS_CREATED, song__release=release_id
    ).count()

    if count > 0:
        tasks.send_song_artist_invite_email.delay(release_id)


def send_release_lifecycle_segment_event(release):
    if release.status == Release.STATUS_APPROVED:
        segment_release_approved(release)
    elif release.status == Release.STATUS_NOT_APPROVED:
        segment_release_not_approved(release)
    elif release.status == Release.STATUS_REJECTED:
        segment_release_rejected(release)
    elif release.status == Release.STATUS_TAKEDOWN:
        segment_release_taken_down(release)
    elif release.status == Release.STATUS_DELETED:
        segment_release_deleted(release)


def trigger_release_updated_events(
    release, initial_release_status, support_release, initial_prepared_status, user
):
    tasks.send_release_status_changed_email.delay(release.id)

    # Create SupportEvent if release has transitioned to prepared
    if support_release and support_release.prepared and not initial_prepared_status:
        SupportEvent.objects.create(
            event=SupportEvent.PREPARED, release=release, user=user
        )

    if initial_release_status != release.status:
        send_release_lifecycle_segment_event(release)

        # Create SupportEvent if release status transitions to Approved or Not Approved from Pending
        if initial_release_status == Release.STATUS_PENDING and release.status in (
            Release.STATUS_APPROVED,
            Release.STATUS_NOT_APPROVED,
        ):
            event = (
                SupportEvent.APPROVED
                if release.status == Release.STATUS_APPROVED
                else SupportEvent.REJECTED
            )
            SupportEvent.objects.create(event=event, release=release, user=user)

        if release.status == Release.STATUS_APPROVED:
            send_royalty_invitations(release.id)
            send_song_artist_invitations(release.id)


def calculate_next_release(current_id: int, assigned_release_ids: List[int]):
    if current_id in assigned_release_ids:
        idx = (assigned_release_ids.index(current_id) + 1) % len(assigned_release_ids)
        return assigned_release_ids[idx]
    return assigned_release_ids[0]


def write_release_history_log(user_id, release, forms, formsets):
    LogEntry.objects.log_action(
        user_id=user_id,
        content_type_id=ContentType.objects.get_for_model(
            release, for_concrete_model=False
        ).pk,
        object_id=release.id,
        object_repr=force_text(release),
        action_flag=ADDITION,
        change_message=construct_change_message(forms, formsets),
    )


def construct_change_message(forms, formsets):
    """
    Construct a JSON structure describing changes from changed objects.
    """
    with translation_override(None):
        change_message = [
            {
                'changed': {
                    'name': str(f._meta.model._meta.verbose_name),
                    'object': str(f.instance),
                    'fields': f.changed_data,
                }
            }
            for f in forms
            if f.changed_data
        ]

        for formset in formsets:
            for added_object in formset.new_objects:
                change_message.append(
                    {
                        'added': {
                            'name': str(added_object._meta.verbose_name),
                            'object': str(added_object),
                        }
                    }
                )
            for changed_object, changed_fields in formset.changed_objects:
                change_message.append(
                    {
                        'changed': {
                            'name': str(changed_object._meta.verbose_name),
                            'object': str(changed_object),
                            'fields': changed_fields,
                        }
                    }
                )
            for deleted_object in formset.deleted_objects:
                change_message.append(
                    {
                        'deleted': {
                            'name': str(deleted_object._meta.verbose_name),
                            'object': str(deleted_object),
                        }
                    }
                )

    return change_message
