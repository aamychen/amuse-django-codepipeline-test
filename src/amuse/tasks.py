import datetime
import hashlib
import json
import os
from contextlib import contextmanager
from time import sleep
from uuid import uuid4

from celery.utils.log import get_task_logger
from django.conf import settings
from django.core.cache import cache
from django.utils import timezone
from djrill import MandrillRecipientsRefused
from oauth2client.client import FlowExchangeError
from waffle import switch_is_active

from amuse import mails, slack, utils
from amuse.vendor.zendesk import api as zendesk
from amuse.analytics import signup_completed
from amuse.celery import app
from amuse.models.bulk_delivery_job import BulkDeliveryJob
from amuse.services import audiorec, lyrics, transcoding, smart_link
from amuse.services.notifications import release_notification_task
from amuse.tokens import user_invitation_token_generator
from amuse.utils import chunks
from amuse.vendor.customerio import CustomerIOException
from amuse.vendor.customerio.events import default as cioevents
from amuse.vendor.segment.events import user_requested_account_delete
from amuse.vendor.spotify import SpotifyAPI
from contenttollgate.mandrill import (
    send_approved_mail,
    send_not_approved_mail,
    send_rejected_mail,
)
from releases import downloads
from releases.asset_labels.builder import ReleaseAssetLabelBuilder
from releases.downloads import GoogleDriveSongFileDownload
from releases.models import CoverArt, Release, ReleaseArtistRole, Song, SongFile
from users import gdpr
from users.helpers import send_royalty_invite
from users.models import RoyaltyInvitation, SongArtistInvitation, TeamInvitation, User

logger = get_task_logger(__name__)
spotifyAPI = SpotifyAPI()


@contextmanager
def task_lock(lock_id, oid, expire=15):
    lock_expire = expire * 60
    yield cache.add(lock_id, oid, lock_expire)


@app.task
def add(x, y):
    return x + y


@app.task
def check_ip():
    import requests

    logger.info(requests.get('https://ipinfo.io').json())


@app.task(bind=True, max_retries=10)
def download_songfileupload_link(self, songfileupload_id):
    try:
        downloads.download_songfileupload_link(songfileupload_id)
    except Exception as exc:
        logger.exception(
            'Failed to download SongFile %s upload link', songfileupload_id
        )
        raise self.retry(exc=exc)


@app.task(bind=True, ignore_result=True)
def post_slack_release_created(self, release):
    try:
        slack.post_release_completed("submitted", release)
    except Exception as exc:
        logger.exception('Could not post release created to Slack for %s', release.pk)
        raise self.retry(exc=exc)


@app.task(bind=True, ignore_result=True)
def post_slack_release_completed(self, release):
    try:
        slack.post_release_completed("received", release)
    except Exception as exc:
        logger.exception('Could not post release completed to Slack for %s', release.pk)
        raise self.retry(exc=exc)


@app.task(bind=True, ignore_result=True)
def post_slack_user_created(self, user):
    try:
        slack.post_user_created(user)
    except Exception as exc:
        logger.exception('Could not post user created to Slack for %s', user.pk)
        raise self.retry(exc=exc)


@app.task(bind=True, ignore_result=True)
def zendesk_create_or_update_user(self, user_id):
    try:
        zendesk.create_or_update_user(user_id)
    except Exception as exc:
        logger.exception('Failed to create or update Zendesk user %s', user_id)
        raise self.retry(exc=exc)


@app.task(bind=True)
def send_password_reset_email(self, user):
    try:
        mails.send_password_reset(user)
    except Exception as exc:
        logger.exception('Failed to send password reset to user %s', user.pk)
        raise self.retry(exc=exc)


@app.task(bind=True)
def send_email_verification_email(self, user):
    try:
        mails.send_email_verification(user)
    except Exception as exc:
        logger.exception('Failed to send email verification to user %s', user.pk)
        raise self.retry(exc=exc)


@app.task(bind=True)
def send_team_member_role_updated_emails(self, data):
    try:
        user_id = data.pop('user_id')
        cioevents().send_team_role_changed_event(user_id, data)
    except CustomerIOException as e:
        logger.exception(f'Failed to send team changed role email. CustomerIO failed.')
        self.retry(exc=e, countdown=60, max_retries=3)


@app.task(bind=True)
def send_team_member_role_removed_emails(self, data):
    try:
        user_id = data.pop('user_id')
        cioevents().send_team_role_removed_event(user_id, data)
    except CustomerIOException as e:
        logger.exception(f'Failed to send team removed role email. CustomerIO failed.')
        self.retry(exc=e, countdown=60, max_retries=3)


@app.task(bind=True)
def send_royalty_owner_notification_email(
    self, user_id, invitee_name, song_name, inviter_first_name, inviter_last_name, rate
):
    try:
        data = {
            'song_name': song_name,
            'invitee_name': invitee_name,
            'inviter_first_name': inviter_first_name,
            'inviter_last_name': inviter_last_name,
            'royalty_rate': f'{rate:.2%}',
        }

        cioevents().send_email_split_release_owner_notification(
            user_id=user_id, data=data
        )
    except CustomerIOException as e:
        logger.exception(
            f'Failed to send royalty notification to the owner. CustomerIO failed.'
        )
        self.retry(exc=e, countdown=60, max_retries=3)


@app.task(bind=True)
def send_royalty_invite_email(self, release_id):
    try:
        invites = RoyaltyInvitation.objects.filter(
            status=RoyaltyInvitation.STATUS_CREATED,
            royalty_split__song__release=release_id,
        ).all()
        release = Release.objects.get(id=release_id)
        primary_artist_role = ReleaseArtistRole.objects.filter(
            release=release, role=ReleaseArtistRole.ROLE_PRIMARY_ARTIST
        ).first()

        for invite in invites:
            split = invite.royalty_split

            payload = {
                'inviter_id': release.user.id,
                'invitee_id': invite.invitee_id,
                'artist_name': primary_artist_role.artist.name,
                'split_id': split.id,
            }
            token = user_invitation_token_generator.make_token(payload)
            send_royalty_invite(invite, split, token)
    except CustomerIOException as e:
        logger.exception(f'Failed to send royalty invites. CustomerIO failed.')
        self.retry(exc=e, countdown=60, max_retries=3)


@app.task(bind=True)
def send_song_artist_invite_email(self, release_id):
    try:
        invites = SongArtistInvitation.objects.filter(
            status=SongArtistInvitation.STATUS_CREATED, song__release=release_id
        ).distinct('email', 'phone_number')

        for invite in invites:
            cioevents().send_song_artist_invite(
                invite.email,
                invite.phone_number,
                {
                    'sender_id': invite.inviter.id,
                    'sender_first_name': invite.inviter.first_name,
                    'sender_last_name': invite.inviter.last_name,
                    'receiver_name': invite.artist.name,
                    'token': invite.token,
                },
            )
            invite.last_sent = timezone.now()
            invite.status = RoyaltyInvitation.STATUS_PENDING
            invite.save()

    except CustomerIOException as e:
        logger.exception(f'Failed to send SongArtist invites. CustomerIO failed.')
        self.retry(exc=e, countdown=60, max_retries=3)


@app.task(bind=True)
def send_team_invite(self, data):
    try:
        email = data.pop('email', None)
        phone = data.pop('phone_number', None)
        invite_id = data.pop('invitation_id')
        invite = TeamInvitation.objects.get(pk=invite_id)

        cioevents().send_team_invite(email, phone, data)
        invite.last_sent = timezone.now()
        invite.save()

    except CustomerIOException as e:
        logger.exception(f'Failed to send team invites. CustomerIO failed.')
        self.retry(exc=e, countdown=60, max_retries=3)


@app.task(bind=True)
def send_release_status_changed_email(self, release_id):
    try:
        release = Release.objects.get(id=release_id)
        if release.status == Release.STATUS_APPROVED:
            send_approved_mail(release)
        elif release.status == Release.STATUS_NOT_APPROVED:
            release_notification_task.delay(release.id)
            send_not_approved_mail(release)
        elif release.status == Release.STATUS_REJECTED:
            send_rejected_mail(release)

    except (Release.DoesNotExist, MandrillRecipientsRefused) as e:
        logger.exception(e)
    except Exception as e:
        logger.exception(
            'Failed to send release status changed email for release %s', release_id
        )
        raise self.retry(
            exc=e, countdown=30 * 60, max_retries=5
        )  # Wait 30 minutes to retry


@app.task(bind=True)
def release_went_pending(self, release_id):
    lock_id = "%s:%s" % (self.__name__, release_id)

    with task_lock(lock_id, self.app.oid, 5) as acquired:
        if acquired:
            from releases.models import Release

            rel = Release.objects.get(pk=release_id)

            if rel.status == Release.STATUS_PENDING:
                try:
                    mails.send_release_pending(rel)
                except Exception as exc:
                    logger.exception(
                        'Failed to send release pending email for release %s',
                        release_id,
                    )
                    raise self.retry(exc=exc)


@app.task(bind=True)
def audiblemagic_identify_file(self, song_file_id):
    if switch_is_active('service:audiblemagic:enabled'):
        from audiblemagic import identify_file
        from releases.models import SongFile

        try:
            identify_file(SongFile.objects.get(pk=song_file_id))
        except Exception as exc:
            logger.exception(
                'Failed to do Audible Magic identification for SongFile %s',
                song_file_id,
            )
            raise self.retry(exc=exc)
    else:
        logger.info("Service audiblemagic is not enabled.")


@app.task(ignore_result=True)
def acrcloud_identify_song(song_id):
    if switch_is_active('service:acrcloud:enabled'):
        from amuse.vendor.acrcloud.id import identify_song
        from releases.models.song import Song

        identify_song(Song.objects.get(pk=song_id))


@app.task(bind=True)
def download_to_bucket(self, url, bucket, bucket_path='', target_extension='audio'):
    """
    Download a file from a URL to an S3 bucket.
    The resulting filename will be a uuid + the given extension.
    :param url: URL to a file
    :param bucket: Bucket name
    :param bucket_path: Path/prefix in bucket
    :param target_extension: File name extension for the resulting file
    :return: The path to the file in the bucket
    """
    write_filename = f'{str(uuid4())}.{target_extension}'
    write_filename_path = os.path.join(bucket_path.strip('/'), write_filename)

    logger.info(
        'Attempting download from URL {} to {}'.format(url, write_filename_path)
    )

    try:
        utils.download_to_bucket(url, bucket, write_filename_path)
        return write_filename_path
    except Exception as e:
        logger.exception('Download to bucket %s failed for URL %s', bucket, url)
        self.retry(countdown=2, exc=e, max_retries=1)


@app.task(bind=True)
def google_drive_to_bucket(
    self, auth_code, file_id, bucket, bucket_path='', target_extension='audio'
):
    """
    Download a file from Google Drive to an S3 bucket.
    The resulting filename will be a uuid + the given extension.
    :param auth_code: Auth code provided by client
    :param file_id: File ID provided by client
    :param bucket: Bucket name
    :param bucket_path: Path/prefix in bucket
    :param target_extension: File name extension for the resulting file
    :return: The path to the file in the bucket
    """
    logger.info(f'Starting Google Drive download of file id {file_id}')

    write_filename = f'{str(uuid4())}.{target_extension}'
    write_filename_path = os.path.join(bucket_path.strip('/'), write_filename)

    try:
        download = GoogleDriveSongFileDownload(auth_code, file_id)
        url = download.get_download_link()
        headers = download.get_headers()

        logger.info(
            'Persisting Google Drive file id {} to {}'.format(
                file_id, write_filename_path
            )
        )

        utils.download_to_bucket(url, bucket, write_filename_path, headers)
        return write_filename_path
    except FlowExchangeError as e:
        logger.warning(
            'Google drive to bucket %s OAuth2 error for file_id %s: %s',
            bucket,
            file_id,
            e,
        )
    except Exception as e:
        logger.exception(
            'Google drive to bucket %s failed for file_id %s', bucket, file_id
        )
        self.retry(countdown=2, exc=e, max_retries=1)


@app.task
def analyze_lyrics(s3_key, song_id):
    if s3_key and switch_is_active('service:lyrics-analysis:enabled'):
        song = Song.objects.get(pk=song_id)
        if not settings.DEBUG and song.meta_audio_locale:
            lyrics.analyze(
                song_id,
                s3_key,
                song.meta_audio_locale.iso_639_1,
                song.get_explicit_display(),
            )
    return s3_key


@app.task
def audio_recognition(s3_key, song_id):
    if s3_key and switch_is_active("service:audio-recognition:enabled"):
        audiorec.recognize(song_id, s3_key)
    return s3_key


@app.task
def transcode(s3_key, song_id):
    """
    Task wrapper for transcoding.transcode. Chainable after
    `download_to_bucket` task.
    :param s3_key: Path to file in audio upload bucket
    :param song_id: Song ID
    :return:
    """
    song = Song.objects.get(pk=song_id)
    if s3_key and not settings.DEBUG:
        transcoding.transcode(song, s3_key)


@app.task(ignore_result=True)
def save_song_file_checksum(song_file_id):
    if not song_file_id:
        logger.warning('Tried to save checksum for empty song file ID')
        return

    song_file = SongFile.objects.get(pk=song_file_id)

    logger.info(
        'Calculating checksum for' ' SongFile %s: %s', song_file_id, song_file.file.name
    )

    try:
        checksum = _calculate_django_file_checksum(song_file.file)
        logger.info('Generated checksum %s for SongFile %s', checksum, song_file_id)
    except Exception:
        logger.exception('Could not calculate checksum for song file %s', song_file_id)
        checksum = None

    if checksum and checksum != song_file.checksum:
        logger.info(
            'Updating checksum for SongFile %s: %s from %s to %s',
            song_file_id,
            song_file.file.name,
            song_file.checksum,
            checksum,
        )
        song_file.checksum = checksum
        song_file.save()

    return (song_file_id, checksum)


@app.task(ignore_result=True)
def save_cover_art_checksum(cover_art_id):
    if not cover_art_id:
        logger.warning('Tried to save checksum for empty cover art ID')
        return

    cover_art = CoverArt.objects.get(pk=cover_art_id)
    logger.info(
        'Calculating checksum for' ' CoverArt %s: %s', cover_art_id, cover_art.file.name
    )

    try:
        checksum = _calculate_django_file_checksum(cover_art.file)
        logger.info('Generated checksum %s for CoverArt %s', checksum, cover_art_id)
    except Exception:
        logger.exception('Could not calculate checksum for cover art %s', cover_art_id)
        checksum = None

    if checksum and checksum != cover_art.checksum:
        logger.info(
            'Updating checksum for CoverArt %s: %s from %s to %s',
            cover_art_id,
            cover_art.file.name,
            cover_art.checksum,
            checksum,
        )
        CoverArt.objects.filter(id=cover_art.id).update(checksum=checksum)

    return (cover_art_id, checksum)


@app.task
def process_coverart(cover_art_id):
    '''Converts cover art to RGB JPEG, generates thumbs and checksum'''
    coverart = CoverArt.objects.filter(pk=cover_art_id).first()
    if not coverart:
        logger.info(f'process_coverart: CoverArt {cover_art_id} does not exist')
        return

    image = coverart.get_file_image()
    if image:
        converted = image
        if image.mode != 'RGB':
            converted = coverart.convert_to_rgb(image)
            logger.info(f'Coverart {cover_art_id} converting to RGB')
        converted = coverart.resize_to_allowed(converted)
        if (
            image.format != 'JPEG'
            or image != converted
            or not coverart.has_correct_file_ending()
        ):
            coverart.save_jpeg_image(converted)
            logger.info(f'Coverart {cover_art_id} saving as JPEG')

        coverart_generate_thumbs.delay(coverart.pk)
    save_cover_art_checksum.delay(coverart.pk)


@app.task(ignore_result=True)
def coverart_generate_thumbs(cover_art_id):
    coverart = CoverArt.objects.filter(pk=cover_art_id).first()
    if not coverart:
        logger.info(f'CoverArt id {cover_art_id} does not exist')
        return

    existing_sizes = set((image.width, image.height) for image in coverart.images.all())

    for size in coverart.file.field.sizes:
        if size not in existing_sizes:
            image = coverart.file.generate_thumbnail(size, 'jpg')
            image.save()
            coverart.images.add(image)


def _calculate_django_file_checksum(file):
    file_hash = hashlib.md5()
    one_mib = 1 * 2**20

    for chunk in file.chunks(one_mib):
        file_hash.update(chunk)

    return file_hash.hexdigest()


@app.task(bind=True)
def add_artist_sequence_to_sar(self, song):
    sar_qs = song.songartistrole_set.all().order_by('role', 'created')
    start = 1
    for sar in sar_qs:
        sar.artist_sequence = start
        sar.save()
        start += 1


@app.task
def delete_minfraud_entries(user_id):
    gdpr.delete_minfraud_entries(user_id=user_id)


@app.task
def delete_artist_v2_history_entries(user_id):
    gdpr.delete_artist_v2_history_entries(user_id=user_id)


@app.task
def clean_transaction_withdrawals(user_id):
    gdpr.clean_transaction_withdrawals(user_id=user_id)


@app.task
def clean_artist_data(user_id):
    gdpr.clean_artist_data(user_id=user_id)


@app.task
def clean_user_data(user_id):
    gdpr.clean_user_data(user_id=user_id)


@app.task
def deactivate_user_newsletter_and_active(user_id):
    gdpr.deactivate_user_newsletter_and_active(user_id=user_id)


@app.task
def delete_user_history_entries(user_id):
    gdpr.delete_user_history_entries(user_id=user_id)


@app.task
def delete_user_from_zendesk(user_id, user_email):
    gdpr.delete_user_from_zendesk(user_id, user_email)


@app.task
def delete_user_from_segment(user_id):
    gdpr.delete_user_from_segment(user_id)


@app.task
def delete_releases_from_fuga(user_id):
    gdpr.delete_releases_from_fuga(user_id)


@app.task
def disable_recurring_adyen_payments(user_id):
    gdpr.disable_recurring_adyen_payments(user_id)


@app.task(bind=True)
def refresh_spotify_artist_images(self, user_id):
    try:
        artists = User.objects.get(id=user_id).artists.all()
        for artist in artists:
            artist.spotify_image = spotifyAPI.fetch_spotify_artist_image_url(
                artist.spotify_id
            )
            artist.save()
    except Exception:
        logger.exception(f"Failed to refresh spotify artist images for user {user_id}")


@app.task(bind=True)
def create_asset_labels(self, release_id):
    release = Release.objects.get(id=release_id)
    builder = ReleaseAssetLabelBuilder(release=release)
    builder.build_labels()


@app.task(bind=True)
def segment_update_is_pro(self, user):
    # dummy task
    pass


@app.task(bind=True)
def send_segment_signup_completed_event(
    self, user, platform_name, detected_country_name, signup_path
):
    signup_completed(user, platform_name, detected_country_name, signup_path)


@app.task(bind=True)
def send_email_first_time_cid_use(self, data):
    try:
        user_id = data.pop('user_id')
        cioevents().send_email_first_time_cid_use(user_id, data)
    except CustomerIOException as e:
        logger.exception(
            f'Failed to send email for first time YouTube Content ID use. CustomerIO failed.'
        )


@app.task(bind=True)
def send_segment_account_delete(self, data):
    user_id = data.pop('user_id')
    user_requested_account_delete(user_id, data)
    # TODO: unused code. Delete it ASAP!


@app.task(time_limit=24 * 60 * 60)  # Time limit of 24 hours to execute the task
def bulk_delivery_job_command(bulk_delivery_job_id):
    logger.info("triggered bulk_delivery_job_command with id %s" % bulk_delivery_job_id)

    job = BulkDeliveryJob.objects.get(pk=bulk_delivery_job_id)
    job.execute()


@app.task
def bulk_delivery_job_command_scheduler():
    items = BulkDeliveryJob.objects.filter(
        status=BulkDeliveryJob.STATUS_CREATED, execute_at__lt=datetime.datetime.utcnow()
    ).values_list('pk', flat=True)

    [bulk_delivery_job_command.delay(job_id) for job_id in items]


@app.task(bind=True)
def smart_links_takedown(self, takedown_release_ids):
    try:
        releases = Release.objects.filter(id__in=takedown_release_ids)

        messages = [
            smart_link.create_release_smart_link_message_payload(release)
            for release in releases
        ]
        for message_batch in chunks(messages, settings.SMART_LINK_MESSAGE_BATCH_SIZE):
            smart_link.send_smart_link_creation_data_to_link_service(message_batch)
    except Exception as ex:
        self.retry(exc=ex, countdown=300, max_retries=3)
