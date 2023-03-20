import sys
import uuid
from datetime import datetime, timedelta
from unittest import mock, skip

import pytest
import responses
from django.core import mail
from django.test import TestCase, override_settings
from django.utils import timezone
from factory import Faker
from oauth2client.client import FlowExchangeError

from amuse import tasks
from amuse.models.bulk_delivery_job import BulkDeliveryJob
from amuse.models.bulk_delivery_job_results import BulkDeliveryJobResult
from amuse.tests.factories import BulkDeliveryJobFactory
from amuse.tests.helpers import (
    ZENDESK_MOCK_API_URL_TOKEN,
    add_zendesk_mock_post_response,
)
from amuse.tokens import user_invitation_token_generator
from amuse.vendor.customerio import CustomerIOException
from amuse.vendor.customerio.events import CustomerIOEvents
from releases.models import Release, ReleaseArtistRole, RoyaltySplit
from releases.tests.factories import (
    CoverArtFactory,
    ReleaseArtistRoleFactory,
    ReleaseFactory,
    RoyaltySplitFactory,
    SongFactory,
    StoreFactory,
    generate_releases,
)
from users.models import RoyaltyInvitation
from users.models.song_artist_invitation import SongArtistInvitation
from users.tests.factories import (
    Artistv2Factory,
    RoyaltyInvitationFactory,
    SongArtistInvitationFactory,
    TeamInvitationFactory,
    UserFactory,
)


@override_settings(**ZENDESK_MOCK_API_URL_TOKEN)
class TaskTestCase(TestCase):
    @mock.patch('amuse.tasks.uuid4', autospec=True)
    @mock.patch('amuse.tasks.logger', autospec=True)
    @mock.patch('amuse.tasks.utils', autospec=True)
    def test_download_to_bucket(self, utils_mock, logger_mock, uuid_mock):
        uuid_mock.return_value = uuid.UUID('1b7267bc-b89b-4a22-a6af-219f0d91a385')

        return_value = tasks.download_to_bucket(
            'http://example.com/file-to-download',
            'my-mock-bucket',
            bucket_path='path/to/file',
            target_extension='wav',
        )

        self.assertEqual(
            return_value, 'path/to/file/1b7267bc-b89b-4a22-a6af-219f0d91a385.wav'
        )

        utils_mock.download_to_bucket.assert_called_with(
            'http://example.com/file-to-download',
            'my-mock-bucket',
            'path/to/file/1b7267bc-b89b-4a22-a6af-219f0d91a385.wav',
        )

        logger_mock.info.assert_called_with(
            'Attempting download from URL http://example.com/file-to-download '
            'to path/to/file/1b7267bc-b89b-4a22-a6af-219f0d91a385.wav'
        )

    @mock.patch('amuse.tasks.uuid4', autospec=True)
    @mock.patch('amuse.tasks.logger', autospec=True)
    @mock.patch('amuse.tasks.utils', autospec=True)
    def test_google_drive_to_bucket(self, utils_mock, logger_mock, uuid_mock):
        uuid_mock.return_value = uuid.UUID('1b7267bc-b89b-4a22-a6af-219f0d91a385')
        with mock.patch.multiple(
            'releases.downloads.GoogleDriveSongFileDownload',
            get_download_link=mock.MagicMock(
                return_value='http://fake-google-download-link'
            ),
            get_headers=mock.MagicMock(
                return_value={'Authorization': 'Bearer 123456 '}
            ),
        ):
            return_value = tasks.google_drive_to_bucket(
                'fake-google-drive-auth-code',
                'fake-google-drive-file-id',
                'my-mock-bucket',
                bucket_path='path/to/file',
                target_extension='wav',
            )

        self.assertEqual(
            return_value, 'path/to/file/1b7267bc-b89b-4a22-a6af-219f0d91a385.wav'
        )

        utils_mock.download_to_bucket.assert_called_with(
            'http://fake-google-download-link',
            'my-mock-bucket',
            'path/to/file/1b7267bc-b89b-4a22-a6af-219f0d91a385.wav',
            {'Authorization': 'Bearer 123456 '},
        )

        logger_mock.info.assert_has_calls(
            [
                mock.call(
                    'Starting Google Drive download of file id fake-google-drive-file-id'
                ),
                mock.call(
                    'Persisting Google Drive file id fake-google-drive-file-id to '
                    'path/to/file/1b7267bc-b89b-4a22-a6af-219f0d91a385.wav'
                ),
            ]
        )

    @mock.patch('amuse.tasks.download_to_bucket.retry')
    @mock.patch('amuse.tasks.utils')
    def test_retry_download_to_bucket(self, mock_utils, mock_retry):
        mock_utils.download_to_bucket.side_effect = error = Exception()
        tasks.download_to_bucket(
            'http://example.com/file-to-download',
            'my-mock-bucket',
            bucket_path='path/to/file',
            target_extension='wav',
        )
        mock_retry.assert_called_with(countdown=2, exc=error, max_retries=1)

    @mock.patch('amuse.tasks.google_drive_to_bucket.retry')
    @mock.patch('amuse.tasks.utils')
    def test_google_drive_to_bucket_retry(self, mock_utils, mock_retry):
        mock_utils.download_to_bucket.side_effect = error = Exception()
        with mock.patch.multiple(
            'releases.downloads.GoogleDriveSongFileDownload',
            get_download_link=mock.MagicMock(
                return_value='http://fake-google-download-link'
            ),
            get_headers=mock.MagicMock(
                return_value={'Authorization': 'Bearer 123456 '}
            ),
        ):
            tasks.google_drive_to_bucket(
                'fake-google-drive-auth-code',
                'fake-google-drive-file-id',
                'my-mock-bucket',
                bucket_path='path/to/file',
                target_extension='wav',
            )
        mock_retry.assert_called_with(countdown=2, exc=error, max_retries=1)

    @mock.patch('amuse.tasks.logger.warning')
    @mock.patch('amuse.tasks.GoogleDriveSongFileDownload.get_download_link')
    def test_google_drive_to_bucket_oauth_error_logged_as_warning(
        self, mock_get_download_link, mock_log_warning
    ):
        file_id = 'file_id'
        bucket = 'bbbbbb'
        error = FlowExchangeError()
        mock_get_download_link.side_effect = error

        tasks.google_drive_to_bucket(
            'auth-code', file_id, bucket, bucket_path='path', target_extension='wav'
        )

        mock_log_warning.assert_called_with(
            'Google drive to bucket %s OAuth2 error for file_id %s: %s',
            bucket,
            file_id,
            error,
        )

    FAKE_TEMPLATE = {
        'code': '<div>editable content</div>',
        'from_email': 'from.email@example.com',
        'subject': None,
    }

    @responses.activate
    @mock.patch('contenttollgate.mandrill.get_template_by_name')
    def test_send_approved_email(self, get_template_mock):
        add_zendesk_mock_post_response()
        get_template_mock.return_value = self.FAKE_TEMPLATE
        release = ReleaseFactory(status=Release.STATUS_APPROVED, error_flags=1)

        mail.outbox = []
        with mock.patch(
            'contenttollgate.mandrill.get_templates_for_release', return_value=[]
        ):
            tasks.send_release_status_changed_email(release.id)

        self.assertEqual(len(mail.outbox), 1)
        sent = mail.outbox[0]
        self.assertEqual(sent.subject, 'Your release has been approved')

    @responses.activate
    @mock.patch('contenttollgate.mandrill.get_template_by_name')
    def test_send_not_approved_email(self, get_template_mock):
        add_zendesk_mock_post_response()
        get_template_mock.return_value = self.FAKE_TEMPLATE
        release = ReleaseFactory(status=Release.STATUS_NOT_APPROVED, error_flags=1)

        mail.outbox = []
        with mock.patch(
            'contenttollgate.mandrill.get_templates_for_release', return_value=[]
        ):
            tasks.send_release_status_changed_email(release.id)

        self.assertEqual(len(mail.outbox), 1)
        sent = mail.outbox[0]
        self.assertEqual(sent.subject, 'Your release is pending')

    @responses.activate
    @mock.patch('contenttollgate.mandrill.get_template_by_name')
    def test_send_rejected_email(self, get_template_mock):
        add_zendesk_mock_post_response()
        get_template_mock.return_value = self.FAKE_TEMPLATE
        release = ReleaseFactory(status=Release.STATUS_REJECTED, error_flags=1)

        mail.outbox = []
        with mock.patch(
            'contenttollgate.mandrill.get_templates_for_release', return_value=[]
        ):
            tasks.send_release_status_changed_email(release.id)

        self.assertEqual(len(mail.outbox), 1)
        sent = mail.outbox[0]
        self.assertEqual(sent.subject, 'Your release has been rejected')

    @responses.activate
    def test_do_not_send_mail_for_other_status(self):
        add_zendesk_mock_post_response()
        release = ReleaseFactory(status=Release.STATUS_DELIVERED, error_flags=1)

        mail.outbox = []
        tasks.send_release_status_changed_email(release.id)
        self.assertEqual(len(mail.outbox), 0)

    @responses.activate
    @mock.patch('amuse.tasks.add_artist_sequence_to_sar', autospec=True)
    def test_tasks_add_artist_sequence_to_sar(
        self, mock_tasks_add_artist_sequence_to_sar
    ):
        add_zendesk_mock_post_response()
        song = SongFactory()
        tasks.add_artist_sequence_to_sar(song)
        mock_tasks_add_artist_sequence_to_sar.assert_called_once_with(song)

    @skip("Skip until cio issue is resolved")
    @responses.activate
    @mock.patch('amuse.tasks.send_royalty_owner_notification_email.retry')
    @mock.patch.object(
        CustomerIOEvents, 'send_email_split_release_owner_notification', autospec=True
    )
    def test_send_royalty_owner_notification_email(self, mock_send, mock_retry):
        add_zendesk_mock_post_response()

        release = ReleaseFactory(created_by=UserFactory())
        song = SongFactory(release=release)

        RoyaltySplitFactory(
            song=song,
            rate=0.8,
            status=RoyaltySplit.STATUS_ACTIVE,
            user=release.created_by,
        )
        split2 = RoyaltySplitFactory(
            song=song, rate=0.2, status=RoyaltySplit.STATUS_ACTIVE
        )

        tasks.send_royalty_owner_notification_email(
            split2.user.id,
            split2.user.get_full_name(),
            split2.song.name,
            release.user.first_name,
            release.user.last_name,
            split2.rate,
        )

        self.assertEqual(1, mock_send.call_count)
        mock_send.assert_called_with(
            tasks.cioevents(),
            split2.user_id,
            {
                'song_name': split2.song.name,
                'invitee_name': split2.user.get_full_name(),
                'inviter_first_name': release.user.first_name,
                'inviter_last_name': release.user.last_name,
                'royalty_rate': '20.00%',
            },
        )

        # test retry
        mock_send.reset_mock()
        mock_send.side_effect = error = CustomerIOException('cio error')
        tasks.send_royalty_owner_notification_email(
            split2.user.id,
            split2.user.get_full_name(),
            split2.song.name,
            release.user.first_name,
            release.user.last_name,
            split2.rate,
        )

        self.assertEqual(1, mock_send.call_count)
        self.assertEqual(1, mock_retry.call_count)
        mock_retry.assert_called_with(exc=error, countdown=60, max_retries=3)

    @skip("Skip until cio issue is resolved")
    @mock.patch.object(CustomerIOEvents, 'send_royalty_invite', autospec=True)
    def test_send_royalty_invite_email_ok(self, mock_send):
        add_zendesk_mock_post_response()

        song = SongFactory()
        primary_artist = Artistv2Factory(name='Primary Artist')
        primary_artist_role = ReleaseArtistRoleFactory(
            release=song.release,
            artist=primary_artist,
            role=ReleaseArtistRole.ROLE_PRIMARY_ARTIST,
        )
        royalty_split_data = {
            'song': song,
            'rate': 1.0,
            'start_date': datetime.today().date(),
        }

        invite = RoyaltyInvitationFactory(
            inviter=UserFactory(artist_name="Zarko"),
            token="123",
            status=RoyaltyInvitation.STATUS_CREATED,
            royalty_split=RoyaltySplitFactory(**royalty_split_data),
            last_sent=timezone.now(),
        )
        payload = {
            'inviter_id': song.release.user.id,
            'invitee_id': invite.invitee_id,
            'artist_name': primary_artist_role.artist.name,
            'split_id': invite.royalty_split.id,
        }
        token = user_invitation_token_generator.make_token(payload)
        with mock.patch.object(
            user_invitation_token_generator, 'make_token', return_value=token
        ):
            tasks.send_royalty_invite_email(song.release.id)

        tasks.send_royalty_invite_email(song.release.id)
        invite.refresh_from_db()
        decoded_token = user_invitation_token_generator.decode_token(invite.token)

        self.assertEqual(invite.status, RoyaltyInvitation.STATUS_PENDING)
        self.assertEqual(decoded_token['inviter_id'], song.release.user.id)
        self.assertEqual(decoded_token['artist_name'], primary_artist.name)
        self.assertEqual(decoded_token['split_id'], invite.royalty_split.id)

        mock_send.assert_called_once_with(
            tasks.cioevents(),
            invite.email,
            invite.phone_number,
            {
                'inviter_id': song.release.user.id,
                'invitee_id': None,
                'invitee_name': invite.name,
                'inviter_first_name': song.release.user.first_name,
                'inviter_last_name': song.release.user.last_name,
                'token': token,
                'song_name': song.name,
                'royalty_rate': '100.00%',
                'expiration_time': invite.expiration_time.strftime("%m/%d/%Y, %H:%M"),
                'release_date': song.release.release_date,
            },
        )

    @responses.activate
    @mock.patch('amuse.tasks.send_royalty_invite_email.retry')
    @mock.patch.object(
        CustomerIOEvents, 'send_royalty_assigned_to_existing_user', autospec=True
    )
    def test_send_royalty_invite_email_to_existing_user(self, mock_send, mock_retry):
        mock_send.side_effect = error = CustomerIOException("cio test exception")

        add_zendesk_mock_post_response()

        song = SongFactory()
        ReleaseArtistRoleFactory(
            release=song.release,
            artist=Artistv2Factory(name='Artist'),
            role=ReleaseArtistRole.ROLE_PRIMARY_ARTIST,
        )
        royalty_split_data = {
            'song': song,
            'rate': 1.0,
            'start_date': datetime.today().date(),
        }

        RoyaltyInvitationFactory(
            inviter=UserFactory(artist_name="Zarko"),
            invitee=UserFactory(),
            token="123",
            status=RoyaltyInvitation.STATUS_CREATED,
            royalty_split=RoyaltySplitFactory(**royalty_split_data),
            last_sent=timezone.now(),
        )

        tasks.send_royalty_invite_email(song.release.id)
        self.assertEqual(mock_send.call_count, 1)
        self.assertEqual(mock_retry.call_count, 1)
        mock_retry.assert_called_with(exc=error, countdown=60, max_retries=3)

    @responses.activate
    @mock.patch.object(CustomerIOEvents, 'send_song_artist_invite', autospec=True)
    def test_send_song_artist_invite_email_ok(self, mock_send):
        add_zendesk_mock_post_response()

        song = SongFactory()
        SongArtistInvitationFactory(
            inviter=UserFactory(artist_name="Zarko Darko"),
            artist=Artistv2Factory(name='I am invited'),
            song=song,
            token='jwt-token',
            status=SongArtistInvitation.STATUS_CREATED,
        )

        tasks.send_song_artist_invite_email(song.release.id)
        self.assertEqual(mock_send.call_count, 1)

    @responses.activate
    @mock.patch('amuse.tasks.send_song_artist_invite_email.retry')
    @mock.patch(
        'amuse.vendor.customerio.events.CustomerIOEvents.send_song_artist_invite'
    )
    def test_send_song_artist_invite_email(self, mock_send, mock_retry):
        mock_send.side_effect = error = CustomerIOException("cio test exception")
        add_zendesk_mock_post_response()

        song = SongFactory()
        SongArtistInvitationFactory(
            inviter=UserFactory(artist_name="Zarko Darko"),
            artist=Artistv2Factory(name='I am invited'),
            song=song,
            token='jwt-token',
            status=SongArtistInvitation.STATUS_CREATED,
        )

        tasks.send_song_artist_invite_email(song.release.id)
        self.assertEqual(mock_send.call_count, 1)
        self.assertEqual(mock_retry.call_count, 1)
        mock_retry.assert_called_with(exc=error, countdown=60, max_retries=3)

    @responses.activate
    @mock.patch.object(CustomerIOEvents, 'send_team_invite', autospec=True)
    def test_send_team_invite_ok(self, mock_send_invite):
        add_zendesk_mock_post_response()
        invite = TeamInvitationFactory()

        data = {
            'email': invite.email,
            'phone_number': invite.phone_number,
            'invitation_id': invite.id,
        }

        tasks.send_team_invite(data)
        self.assertEqual(mock_send_invite.call_count, 1)

    @responses.activate
    @mock.patch('amuse.tasks.send_team_invite.retry')
    @mock.patch('amuse.vendor.customerio.events.CustomerIOEvents.send_team_invite')
    def test_send_team_invite(self, mock_send_invite, mock_retry):
        mock_send_invite.side_effect = error = CustomerIOException("cio test exception")

        add_zendesk_mock_post_response()
        invite = TeamInvitationFactory()

        data = {
            'email': invite.email,
            'phone_number': invite.phone_number,
            'invitation_id': invite.id,
        }

        tasks.send_team_invite(data)
        self.assertEqual(mock_retry.call_count, 1)
        mock_retry.assert_called_with(exc=error, countdown=60, max_retries=3)

    @responses.activate
    @mock.patch.object(CustomerIOEvents, 'send_team_role_changed_event', autospec=True)
    def test_send_team_member_role_updated_emails_ok(self, mock_send):
        add_zendesk_mock_post_response()

        data = {'user_id': 123}

        tasks.send_team_member_role_updated_emails(data)
        self.assertEqual(mock_send.call_count, 1)

    @responses.activate
    @mock.patch('amuse.tasks.send_team_member_role_updated_emails.retry')
    @mock.patch(
        'amuse.vendor.customerio.events.CustomerIOEvents.send_team_role_changed_event'
    )
    def test_send_team_member_role_updated_emails(self, mock_send, mock_retry):
        mock_send.side_effect = error = CustomerIOException("cio test exception")

        add_zendesk_mock_post_response()

        data = {'user_id': 123}

        tasks.send_team_member_role_updated_emails(data)
        self.assertEqual(mock_retry.call_count, 1)
        mock_retry.assert_called_with(exc=error, countdown=60, max_retries=3)

    @responses.activate
    @mock.patch.object(CustomerIOEvents, 'send_team_role_removed_event', autospec=True)
    def test_send_team_member_role_removed_emails_ok(self, mock_send):
        add_zendesk_mock_post_response()

        data = {'user_id': 123}

        tasks.send_team_member_role_removed_emails(data)
        self.assertEqual(mock_send.call_count, 1)

    @responses.activate
    @mock.patch('amuse.tasks.send_team_member_role_removed_emails.retry')
    @mock.patch(
        'amuse.vendor.customerio.events.CustomerIOEvents.send_team_role_removed_event'
    )
    def test_send_team_member_role_removed_emails(self, mock_send, mock_retry):
        mock_send.side_effect = error = CustomerIOException("cio test exception")

        add_zendesk_mock_post_response()

        data = {'user_id': 123}

        tasks.send_team_member_role_removed_emails(data)
        self.assertEqual(mock_retry.call_count, 1)
        mock_retry.assert_called_with(exc=error, countdown=60, max_retries=3)

    @responses.activate
    @mock.patch(
        'amuse.vendor.spotify.spotify_api.SpotifyAPI.fetch_spotify_artist_image_url'
    )
    def test_refresh_spotify_artist_images_ok(self, mock_spotify):
        add_zendesk_mock_post_response()

        url = 'https://fake.image/url.jpg'
        mock_spotify.return_value = url

        user = UserFactory(artist_name=Faker('name'))
        user.create_artist_v2(name=user.artist_name, spotify_id='123')
        user.create_artist_v2(name=user.artist_name, spotify_id='124')

        tasks.refresh_spotify_artist_images(user.id)

        self.assertEqual(2, mock_spotify.call_count)
        for artist in user.artists.all():
            self.assertEqual(url, artist.spotify_image)

    @responses.activate
    @mock.patch('amuse.tasks.logger', autospec=True)
    @mock.patch(
        'amuse.vendor.spotify.spotify_api.SpotifyAPI.fetch_spotify_artist_image_url'
    )
    def test_refresh_spotify_artist_images(self, mock_spotify, mock_logger):
        mock_spotify.side_effect = error = Exception("exception")

        user = UserFactory(artist_name=Faker('name'))
        user.create_artist_v2(name=user.artist_name, spotify_id='123')
        user.create_artist_v2(name=user.artist_name, spotify_id='124')

        tasks.refresh_spotify_artist_images(user.id)

        mock_logger.exception.assert_has_calls(
            [mock.call(f"Failed to refresh spotify artist images for user {user.id}")]
        )

    @mock.patch('amuse.tasks.logger')
    def test_save_cover_art_checksum_handles_no_cover_art_id(self, mock_logger):
        tasks.save_cover_art_checksum(None)
        mock_logger.warning.assert_has_calls(
            [mock.call("Tried to save checksum for empty cover art ID")]
        )

    @responses.activate
    @mock.patch("amuse.tasks._calculate_django_file_checksum")
    @mock.patch('amuse.tasks.logger')
    @mock.patch('amuse.tasks.zendesk_create_or_update_user')
    def test_save_cover_art_checksum_handles_checksum_error(
        self, mock_zendesk, mock_logger, mock_calculate_checksum
    ):
        mock_calculate_checksum.side_effect = Exception()
        cover_art = CoverArtFactory()

        cover_art_id, checksum = tasks.save_cover_art_checksum(cover_art.id)

        assert checksum is None
        mock_logger.exception.assert_has_calls(
            [mock.call("Could not calculate checksum for cover art %s", cover_art.id)]
        )

    @responses.activate
    @mock.patch('amuse.tasks.create_asset_labels', autospec=True)
    def test_tasks_build_asset_labels(self, mock_tasks_create_asset_labels):
        add_zendesk_mock_post_response()
        release = ReleaseFactory()
        tasks.create_asset_labels(release.id)
        mock_tasks_create_asset_labels.assert_called_once_with(release.id)

    @responses.activate
    @mock.patch(
        'amuse.vendor.customerio.events.CustomerIOEvents.send_email_first_time_cid_use'
    )
    def test_send_email_first_time_cid_use(self, mock_cio_event):
        user = UserFactory(
            first_name='Neko', last_name='Nekic', email='test@example.com'
        )
        data = {
            "user_id": user.id,
            "recipient": user.email,
            "receiver_first_name": user.first_name,
            "receiver_last_name": user.last_name,
        }

        tasks.send_email_first_time_cid_use(data)

        self.assertEqual(mock_cio_event.call_count, 1)

    @responses.activate
    @mock.patch('amuse.tasks.logger', autospec=True)
    @mock.patch(
        'amuse.vendor.customerio.events.CustomerIOEvents.send_email_first_time_cid_use'
    )
    def test_send_email_first_time_cid_use_error(self, mock_cio_event, mock_logger):
        mock_cio_event.side_effect = error = CustomerIOException()
        user = UserFactory(
            first_name='Neko', last_name='Nekic', email='test@example.com'
        )
        data = {
            "user_id": user.id,
            "recipient": user.email,
            "receiver_first_name": user.first_name,
            "receiver_last_name": user.last_name,
        }

        tasks.send_email_first_time_cid_use(data)

        mock_logger.exception.assert_has_calls(
            [
                mock.call(
                    f'Failed to send email for first time YouTube Content ID use. CustomerIO failed.'
                )
            ]
        )

    @responses.activate
    @mock.patch('amuse.tasks.send_segment_signup_completed_event')
    def test_send_signup_completed(self, mock_signup_completed):
        platform_name = 'web'
        country = 'Congo, Democratic Republic of'
        signup_path = 'regular'
        user = UserFactory(
            first_name='Neko', last_name='Nekic', email='test@example.com'
        )

        tasks.send_segment_signup_completed_event(
            user, platform_name, country, signup_path
        )

        self.assertEqual(mock_signup_completed.call_count, 1)
        mock_signup_completed.assert_called_once_with(
            user, platform_name, country, signup_path
        )

    @mock.patch('amuse.tasks.send_segment_account_delete')
    def test_send_user_requested_delete(self, mock_task):
        add_zendesk_mock_post_response()
        user = UserFactory(
            first_name='Neko', last_name='Nekic', email='test@example.com'
        )
        data = {
            "user_id": user.id,
            "user_email": user.email,
            "user_first_name": user.first_name,
            "user_last_name": user.last_name,
            "delete_requested_at": datetime.now(),
        }

        tasks.send_segment_account_delete(data)

        mock_task.assert_called_once_with(data)


@pytest.mark.django_db
@mock.patch("amuse.tasks.sleep")
@mock.patch("amuse.models.bulk_delivery_job.time.sleep")
@mock.patch("amuse.services.delivery.helpers.sleep")
@mock.patch("amuse.tasks.zendesk_create_or_update_user")
@mock.patch("amuse.services.delivery.helpers.sqs.send_message")
def test_trigger_delivery_command_successful_batches(mock_send_message, *args):
    # Initiatlize stores
    spotify_store = StoreFactory(
        name="Spotify", internal_name="spotify", multi_batch_support=False
    )

    # Create a bunch of releases
    num_releases = 2  # Bigger than a single batch_size
    releases = generate_releases(num_releases, Release.STATUS_APPROVED)
    assert len(releases) == num_releases

    # Initialize BulkDeliveryJob
    job = BulkDeliveryJobFactory()
    job.store = spotify_store
    job.save()

    # Mock getting the release_ids from file
    release_ids = sorted([release.id for release in releases])

    def get_release_and_song_ids(_):
        return [], release_ids

    with mock.patch(
        'amuse.models.bulk_delivery_job.BulkDeliveryJob.get_release_and_song_ids',
        get_release_and_song_ids,
    ) as mock_release_ids_from_file:
        tasks.bulk_delivery_job_command(job.id)
        results = BulkDeliveryJobResult.objects.filter(job_id=job.id)
        assert results.count() == len(releases)
        for result in results:
            assert result.status == BulkDeliveryJobResult.STATUS_SUCCESSFUL
            assert result.description == 'Operation was successfully triggered'
            assert result.release_id in release_ids


@pytest.mark.django_db
@mock.patch("amuse.tasks.sleep")
@mock.patch("amuse.models.bulk_delivery_job.time.sleep")
@mock.patch("amuse.services.delivery.helpers.sleep")
@mock.patch("amuse.tasks.zendesk_create_or_update_user")
@mock.patch("amuse.services.delivery.helpers.sqs.send_message")
def test_trigger_delivery_command_invalid_coverart_checksum(mock_send_message, *args):
    spotify_store = StoreFactory(name="Spotify", internal_name="spotify")

    # Create a bunch of releases
    num_releases = 12  # Bigger than a single batch_size
    releases = generate_releases(num_releases, Release.STATUS_APPROVED)
    assert len(releases) == num_releases

    # Make the first release a release with an invalid coverart checksum
    releases[0].cover_art.checksum = "Invalid checksum"
    with mock.patch('amuse.tasks.process_coverart'):
        releases[0].cover_art.save()
    failed_release_id = releases[0].id

    # Initialize BulkDeliveryJob
    job = BulkDeliveryJobFactory()
    job.store = spotify_store
    job.save()

    # Mock getting the release_ids from file
    release_ids = sorted([release.id for release in releases])

    def get_release_and_song_ids(_):
        return [], release_ids

    with mock.patch(
        'amuse.models.bulk_delivery_job.BulkDeliveryJob.get_release_and_song_ids',
        get_release_and_song_ids,
    ) as mock_release_ids_from_file:
        tasks.bulk_delivery_job_command(job.id)
        results = BulkDeliveryJobResult.objects.filter(
            job_id=job.id, status=BulkDeliveryJobResult.STATUS_SUCCESSFUL
        )
        assert results.count() == len(releases) - 1
        for result in results:
            assert result.status == BulkDeliveryJobResult.STATUS_SUCCESSFUL
            assert result.description == 'Operation was successfully triggered'
            assert result.release_id in release_ids
            assert result.release_id != failed_release_id

        results = BulkDeliveryJobResult.objects.filter(
            job_id=job.id, status=BulkDeliveryJobResult.STATUS_FAILED
        )
        assert results.count() == 1
        assert results[0].release_id == failed_release_id
        assert results[0].status == BulkDeliveryJobResult.STATUS_FAILED
        assert (
            results[0].description
            == 'Operation failed due to invalid coverart checksum'
        )


@pytest.mark.django_db
@mock.patch("amuse.tasks.bulk_delivery_job_command.delay")
def test_bulk_delivery_job_command_scheduler(mock_delay):
    BulkDeliveryJobFactory(execute_at=None)
    scheduled_job = BulkDeliveryJobFactory(
        execute_at=datetime.utcnow() - timedelta(days=1)
    )
    BulkDeliveryJobFactory(
        status=BulkDeliveryJob.STATUS_PROCESSING,
        execute_at=datetime.utcnow() - timedelta(days=1),
    )
    BulkDeliveryJobFactory(execute_at=datetime.utcnow() + timedelta(days=1))

    tasks.bulk_delivery_job_command_scheduler()
    mock_delay.assert_called_once_with(scheduled_job.pk)


@pytest.mark.django_db
@override_settings(SMART_LINK_MESSAGE_BATCH_SIZE=3)
@mock.patch("django.db.models.signals.ModelSignal.send")
@mock.patch("amuse.services.smart_link.send_smart_link_creation_data_to_link_service")
def test_smart_links_takedown(mock_send, _):
    releases = []
    for _ in range(0, 4):
        release = ReleaseFactory(
            status=Release.STATUS_TAKEDOWN, type=Release.TYPE_ALBUM
        )

        CoverArtFactory(release=release, user=release.user, file__filename='cover.jpg')
        releases.append(release)

    tasks.smart_links_takedown([release.id for release in releases])
    assert mock_send.call_count == 2
