import json

import responses
from django.conf import settings
from django.test import override_settings, TransactionTestCase
from django.urls import reverse_lazy as reverse
from waffle.models import Switch

from amuse.models import Transcoding
from amuse.storages import S3Storage
from amuse.tests.factories import TranscodingFactory
from amuse.tests.helpers import (
    ZENDESK_MOCK_API_URL_TOKEN,
    add_zendesk_mock_post_response,
    build_auth_header,
)
from releases.models import SongFile
from releases.tests.factories import SongFileFactory


@override_settings(**ZENDESK_MOCK_API_URL_TOKEN)
class ElasticTranscodingServiceTestCase(TransactionTestCase):
    @responses.activate
    def setUp(self):
        add_zendesk_mock_post_response()
        self.callback_url = reverse("song_file_transcoder_state_change")
        self.transcoding = TranscodingFactory()

    def notification(self, *, state=None, flac_key=None, mp3_key=None):
        message = {
            "jobId": self.transcoding.transcoder_job,
            "state": Transcoding.external_status(state or Transcoding.STATUS_SUBMITTED),
            "outputs": [
                {
                    "presetId": settings.AWS_FLAC_PRESET_ID,
                    "duration": "123",
                    "key": flac_key or "flac.flac",
                },
                {
                    "presetId": settings.AWS_MP3128K_PRESET_ID,
                    "duration": "123",
                    "key": mp3_key or "mp3.mp3",
                },
            ],
        }
        return {"Type": "Notification", "Message": json.dumps(message)}

    def create_transcoded_file_on_storage(self, key, infile):
        storage = S3Storage(bucket_name=settings.AWS_SONG_FILE_TRANSCODED_BUCKET_NAME)
        with storage.open(key, "wb") as f:
            f.write(open(infile, "rb").read())

    def test_callback(self):
        notification = self.notification()
        response = self.client.post(
            self.callback_url, json.dumps(notification), content_type="application/json"
        )

        assert response.status_code == 200

    def test_callback_handles_state_change(self):
        assert self.transcoding.status == Transcoding.STATUS_SUBMITTED
        notification = self.notification(state=Transcoding.STATUS_PROGRESSING)
        self.client.post(
            self.callback_url, json.dumps(notification), content_type="application/json"
        )

        self.transcoding.refresh_from_db()
        assert self.transcoding.status == Transcoding.STATUS_PROGRESSING

    def test_callback_creates_songfiles_on_completed_when_ats_is_inactive(self):
        Switch.objects.create(name='service:audio-transcoder:enabled', active=False)
        self.create_transcoded_file_on_storage(
            "flac.flac", "amuse/tests/test_api/data/flac.flac"
        )
        self.create_transcoded_file_on_storage(
            "mp3.mp3", "amuse/tests/test_api/data/mp3.mp3"
        )
        assert self.transcoding.song.files.count() == 0

        notification = self.notification(state=Transcoding.STATUS_COMPLETED)
        self.client.post(
            self.callback_url, json.dumps(notification), content_type="application/json"
        )

        assert self.transcoding.song.files.count() == 2

    def test_callback_doesnt_creates_songfiles_on_completed_when_ats_is_active(self):
        Switch.objects.create(name='service:audio-transcoder:enabled', active=True)
        self.create_transcoded_file_on_storage(
            "flac.flac", "amuse/tests/test_api/data/flac.flac"
        )
        self.create_transcoded_file_on_storage(
            "mp3.mp3", "amuse/tests/test_api/data/mp3.mp3"
        )
        assert self.transcoding.song.files.count() == 0

        notification = self.notification(state=Transcoding.STATUS_COMPLETED)
        self.client.post(
            self.callback_url, json.dumps(notification), content_type="application/json"
        )

        assert self.transcoding.song.files.count() == 0

    def test_callback_updates_existing_songfiles_on_update_when_ats_is_inactive(self):
        Switch.objects.create(name='service:audio-transcoder:enabled', active=False)
        flac = SongFileFactory(type=SongFile.TYPE_FLAC, song=self.transcoding.song)
        mp3 = SongFileFactory(type=SongFile.TYPE_MP3, song=self.transcoding.song)

        self.create_transcoded_file_on_storage(
            "updated.mp3", "amuse/tests/test_api/data/mp3.mp3"
        )
        self.create_transcoded_file_on_storage(
            "updated.flac", "amuse/tests/test_api/data/flac.flac"
        )

        notification = self.notification(
            state=Transcoding.STATUS_COMPLETED,
            flac_key="updated.flac",
            mp3_key="updated.mp3",
        )
        self.client.post(
            self.callback_url, json.dumps(notification), content_type="application/json"
        )

        assert self.transcoding.song.files.count() == 2
        assert (
            self.transcoding.song.files.get(type=SongFile.TYPE_FLAC).file.name
            == "updated.flac"
        )
        assert (
            self.transcoding.song.files.get(type=SongFile.TYPE_MP3).file.name
            == "updated.mp3"
        )

    def test_callback_doesnt_updates_existing_songfiles_on_update_when_ats_is_active(
        self,
    ):
        Switch.objects.create(name='service:audio-transcoder:enabled', active=True)
        flac = SongFileFactory(type=SongFile.TYPE_FLAC, song=self.transcoding.song)
        mp3 = SongFileFactory(type=SongFile.TYPE_MP3, song=self.transcoding.song)

        self.create_transcoded_file_on_storage(
            "updated.mp3", "amuse/tests/test_api/data/mp3.mp3"
        )
        self.create_transcoded_file_on_storage(
            "updated.flac", "amuse/tests/test_api/data/flac.flac"
        )

        notification = self.notification(
            state=Transcoding.STATUS_COMPLETED,
            flac_key="updated.flac",
            mp3_key="updated.mp3",
        )
        self.client.post(
            self.callback_url, json.dumps(notification), content_type="application/json"
        )

        assert self.transcoding.song.files.count() == 2
        assert (
            self.transcoding.song.files.get(type=SongFile.TYPE_FLAC).file.name
            != "updated.flac"
        )
        assert (
            self.transcoding.song.files.get(type=SongFile.TYPE_MP3).file.name
            != "updated.mp3"
        )

    def test_transcoder_name_is_set(self):
        assert self.transcoding.transcoder_name == Transcoding.ELASTIC_TRANSCODER


@override_settings(**ZENDESK_MOCK_API_URL_TOKEN)
class AudioTranscoderServiceTestCase(TransactionTestCase):
    @responses.activate
    def setUp(self):
        add_zendesk_mock_post_response()
        self.callback_url = reverse("sns_notification")
        self.transcoding = TranscodingFactory(
            transcoder_name=Transcoding.AUDIO_TRANSCODER_SERVICE
        )
        self.headers = build_auth_header(
            settings.AWS_SNS_USER, settings.AWS_SNS_PASSWORD
        )

    def notification(self, status=None, bucket=None, flac_key=None, mp3_key=None):
        message = {
            "id": self.transcoding.id,
            "status": None or status,
            "outputs": [
                {
                    "key": flac_key or "flac.flac",
                    "format": "flac",
                    "bucket": bucket or "bucket_name",
                    "duration": "123",
                },
                {
                    "key": mp3_key or "mp3.mp3",
                    "format": "mp3",
                    "bucket": bucket or "bucket_name",
                    "duration": "123",
                },
            ],
            "errors": None,
        }
        return {
            "Type": "Notification",
            "TopicArn": settings.AUDIO_TRANSCODER_SERVICE_RESPONSE_TOPIC,
            "Message": json.dumps(message),
        }

    def create_transcoded_file_on_storage(self, key, infile):
        storage = S3Storage(bucket_name=settings.AWS_SONG_FILE_TRANSCODED_BUCKET_NAME)
        with storage.open(key, "wb") as f:
            f.write(open(infile, "rb").read())

    def test_callback(self):
        notification = self.notification()
        response = self.client.post(
            self.callback_url,
            json.dumps(notification),
            content_type="application/json",
            **self.headers,
        )

        assert response.status_code == 200

    def test_callback_handles_completed(self):
        assert self.transcoding.status == Transcoding.STATUS_SUBMITTED
        notification = self.notification(status='success')
        self.client.post(
            self.callback_url,
            json.dumps(notification),
            content_type="application/json",
            **self.headers,
        )

        self.transcoding.refresh_from_db()
        assert self.transcoding.status == Transcoding.STATUS_COMPLETED

    def test_callback_handles_error(self):
        assert self.transcoding.status == Transcoding.STATUS_SUBMITTED
        notification = self.notification(status='error')
        self.client.post(
            self.callback_url,
            json.dumps(notification),
            content_type="application/json",
            **self.headers,
        )

        self.transcoding.refresh_from_db()
        assert self.transcoding.status == Transcoding.STATUS_ERROR

    def test_callback_create_songfiles_on_completed_when_ats_is_active(self):
        Switch.objects.create(name='service:audio-transcoder:enabled', active=True)
        self.create_transcoded_file_on_storage(
            "flac.flac", "amuse/tests/test_api/data/flac.flac"
        )
        self.create_transcoded_file_on_storage(
            "mp3.mp3", "amuse/tests/test_api/data/mp3.mp3"
        )
        assert self.transcoding.song.files.count() == 0

        notification = self.notification(status='success')
        self.client.post(
            self.callback_url,
            json.dumps(notification),
            content_type="application/json",
            **self.headers,
        )

        assert self.transcoding.song.files.count() == 2

    def test_callback_doesnt_create_songfiles_on_completed_when_ats_is_inactive(self):
        Switch.objects.create(name='service:audio-transcoder:enabled', active=False)
        self.create_transcoded_file_on_storage(
            "flac.flac", "amuse/tests/test_api/data/flac.flac"
        )
        self.create_transcoded_file_on_storage(
            "mp3.mp3", "amuse/tests/test_api/data/mp3.mp3"
        )
        assert self.transcoding.song.files.count() == 0

        notification = self.notification(status='success')
        self.client.post(
            self.callback_url,
            json.dumps(notification),
            content_type="application/json",
            **self.headers,
        )

        assert self.transcoding.song.files.count() == 0

    def test_callback_updates_existing_songfiles_on_update_when_ats_is_active(self):
        Switch.objects.create(name='service:audio-transcoder:enabled', active=True)
        flac = SongFileFactory(type=SongFile.TYPE_FLAC, song=self.transcoding.song)
        mp3 = SongFileFactory(type=SongFile.TYPE_MP3, song=self.transcoding.song)

        self.create_transcoded_file_on_storage(
            "updated.mp3", "amuse/tests/test_api/data/mp3.mp3"
        )
        self.create_transcoded_file_on_storage(
            "updated.flac", "amuse/tests/test_api/data/flac.flac"
        )

        notification = self.notification(
            status='success', flac_key="updated.flac", mp3_key="updated.mp3"
        )
        self.client.post(
            self.callback_url,
            json.dumps(notification),
            content_type="application/json",
            **self.headers,
        )

        assert self.transcoding.song.files.count() == 2
        assert (
            self.transcoding.song.files.get(type=SongFile.TYPE_FLAC).file.name
            == "updated.flac"
        )
        assert (
            self.transcoding.song.files.get(type=SongFile.TYPE_MP3).file.name
            == "updated.mp3"
        )

    def test_callback_doesnt_updates_existing_songfiles_on_update_when_ats_is_inactive(
        self,
    ):
        Switch.objects.create(name='service:audio-transcoder:enabled', active=False)
        flac = SongFileFactory(type=SongFile.TYPE_FLAC, song=self.transcoding.song)
        mp3 = SongFileFactory(type=SongFile.TYPE_MP3, song=self.transcoding.song)

        self.create_transcoded_file_on_storage(
            "updated.mp3", "amuse/tests/test_api/data/mp3.mp3"
        )
        self.create_transcoded_file_on_storage(
            "updated.flac", "amuse/tests/test_api/data/flac.flac"
        )

        notification = self.notification(
            status='success', flac_key="updated.flac", mp3_key="updated.mp3"
        )
        self.client.post(
            self.callback_url,
            json.dumps(notification),
            content_type="application/json",
            **self.headers,
        )

        assert self.transcoding.song.files.count() == 2
        assert (
            self.transcoding.song.files.get(type=SongFile.TYPE_FLAC).file.name
            != "updated.flac"
        )
        assert (
            self.transcoding.song.files.get(type=SongFile.TYPE_MP3).file.name
            != "updated.mp3"
        )

    def test_transcoder_name_is_set(self):
        assert self.transcoding.transcoder_name == Transcoding.AUDIO_TRANSCODER_SERVICE
