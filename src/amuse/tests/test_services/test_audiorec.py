import json
from unittest import mock

import responses
from django.conf import settings
from django.test import TestCase, override_settings
from django.urls import reverse_lazy as reverse

from amuse.services.audiorec import MIN_SCORE, recognize
from amuse.tests.helpers import (
    ZENDESK_MOCK_API_URL_TOKEN,
    add_zendesk_mock_post_response,
    build_auth_header,
)
from releases.tests.factories import SongFactory


RESULT = {
    "score": 100,
    "offset": 20,
    "artist_name": "Test Artist",
    "album_title": "Test Album",
    "track_title": "Test Track",
    "match_upc": "0000000000001",
    "match_isrc": "NULL000000001",
    "external_metadata": json.dumps({"foo": "bar"}),
}


@override_settings(**ZENDESK_MOCK_API_URL_TOKEN)
class AudioRecognitionServiceTestCase(TestCase):
    def setUp(self):
        with mock.patch('amuse.tasks.zendesk_create_or_update_user'):
            self.song = SongFactory()
        self.url = reverse("sns_notification")
        self.headers = build_auth_header(
            settings.AWS_SNS_USER, settings.AWS_SNS_PASSWORD
        )

    @mock.patch("amuse.vendor.aws.sqs.send_message")
    def test_recognize_sends_message(self, mock_sqs):
        assert recognize(123, "foo.wav")
        mock_sqs.assert_called_once_with(
            settings.AUDIO_RECOGNITION_SERVICE_REQUEST_QUEUE,
            {
                "id": 123,
                "bucket": settings.AWS_SONG_FILE_UPLOADED_BUCKET_NAME,
                "path": "",
                "filename": "foo.wav",
            },
        )

    def notification(self, song_id, results=[], errors=[]):
        return {
            "Type": "Notification",
            "TopicArn": settings.AUDIO_RECOGNITION_SERVICE_RESPONSE_TOPIC,
            "Message": json.dumps(
                {"id": song_id, "results": results, "errors": errors}
            ),
        }

    @responses.activate
    @override_settings(AUDIO_RECOGNITION_SERVICE_RESPONSE_TOPIC="topic")
    def test_sns_callback(self):
        notification = self.notification(
            self.song.id, [{"id": self.song.id, **RESULT}], []
        )
        response = self.client.post(
            self.url,
            json.dumps(notification),
            content_type="application/json",
            **self.headers,
        )
        assert response.status_code == 200
        assert self.song.acrcloud_matches.count() == 1

    @responses.activate
    def test_sns_callback_adheres_to_min_score(self):
        notification = self.notification(
            self.song.id, [{"id": self.song.id, **RESULT, "score": MIN_SCORE - 1}]
        )
        response = self.client.post(
            self.url,
            json.dumps(notification),
            content_type="application/json",
            **self.headers,
        )
        assert response.status_code == 200
        assert self.song.acrcloud_matches.count() == 0
