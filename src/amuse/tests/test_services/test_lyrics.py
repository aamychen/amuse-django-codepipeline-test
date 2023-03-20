import json
from unittest import mock

import responses
from django.conf import settings
from django.test import TestCase, override_settings
from django.urls import reverse_lazy as reverse
from rest_framework.test import APITestCase

from amuse.services.lyrics import analyze
from amuse.tests.helpers import (
    ZENDESK_MOCK_API_URL_TOKEN,
    add_zendesk_mock_post_response,
    build_auth_header,
)
from releases.tests.factories import SongFactory


@override_settings(**ZENDESK_MOCK_API_URL_TOKEN)
class LyricsServiceIntegrationTestCase(TestCase):
    @mock.patch("amuse.vendor.aws.sqs.send_message", autospec=True)
    def test_only_analyze_en(self, mock_send_message):
        assert not analyze(123, "test.wav", "sv", 'clean')
        mock_send_message.assert_not_called()

    @mock.patch("amuse.vendor.aws.sqs.send_message", autospec=True)
    def test_not_analyze_explicit(self, mock_send_message):
        assert not analyze(123, "test.wav", "en", "explicit")
        mock_send_message.assert_not_called()

    @override_settings(
        LYRICS_SERVICE_REQUEST_QUEUE="queue",
        AWS_SONG_FILE_UPLOADED_BUCKET_NAME="bucket",
    )
    @mock.patch("amuse.vendor.aws.sqs.send_message", autospec=True)
    def test_analyze_sends_message(self, mock_send_message):
        assert analyze(123, "foo.wav", "en", "clean")
        mock_send_message.assert_called_once_with(
            settings.LYRICS_SERVICE_REQUEST_QUEUE,
            {
                "id": 123,
                "bucket": settings.AWS_SONG_FILE_UPLOADED_BUCKET_NAME,
                "path": "",
                "filename": "foo.wav",
                "language": "en-US",
            },
        )

    @mock.patch("amuse.vendor.aws.sqs.send_message", autospec=True)
    def test_analyze_explicit_clean(self, mock_send_message):
        assert analyze(123, "test.wav", "en", "clean")
        mock_send_message.call_count == 1

    @mock.patch("amuse.vendor.aws.sqs.send_message", autospec=True)
    def test_analyze_explicit_none(self, mock_send_message):
        assert analyze(123, "test.wav", "en", "none")
        mock_send_message.call_count == 1

    @responses.activate
    @override_settings(LYRICS_SERVICE_RESPONSE_TOPIC="topic")
    def test_sns_callback(self):
        add_zendesk_mock_post_response()
        song = SongFactory()
        url = reverse("sns_notification")
        notification = {
            "Type": "Notification",
            "TopicArn": settings.LYRICS_SERVICE_RESPONSE_TOPIC,
            "Message": json.dumps(
                {"id": song.id, "explicit": True, "text": "foo bar b**"}
            ),
        }
        response = self.client.post(
            url,
            json.dumps(notification),
            content_type="application/json",
            **build_auth_header(settings.AWS_SNS_USER, settings.AWS_SNS_PASSWORD),
        )
        assert song.lyricsanalysisresult.explicit == True
        assert song.lyricsanalysisresult.text == "foo bar b**"
