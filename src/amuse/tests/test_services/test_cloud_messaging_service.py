import responses
import json
from rest_framework import status
from django.conf import settings
from unittest.mock import patch
from django.test import TestCase
from django.core.cache import cache
from amuse.services.notifications import (
    CloudMessagingService,
    release_notification_task,
)
from amuse.models.utils import NotificationTemplate
from users.tests.factories import UserFactory
from releases.tests.factories import ReleaseFactory
from waffle.models import Switch
from waffle.testutils import override_switch


class TestCloudMessagingService(TestCase):
    @patch("amuse.tasks.zendesk_create_or_update_user")
    def setUp(self, mock_task):
        self.user = UserFactory(firebase_token='123456')
        self.cms_instance = CloudMessagingService()
        self.default_template = NotificationTemplate.objects.create(
            name='test_template',
            data={
                "key": "test:template",
                "body": "Hello {{test_param}}",
                "title": "Greeting",
            },
        )
        Switch.objects.all().delete()
        cache.clear()

    def test_get_template(self):
        template = self.cms_instance.get_template('test:template')
        self.assertIsNotNone(template)
        self.assertIsInstance(template, NotificationTemplate)

    def test_render(self):
        expected = "Hello JohnDoe"
        template = self.cms_instance.get_template('test:template')
        content = self.cms_instance.render(
            template.data['body'], {"test_param": "JohnDoe"}
        )
        self.assertEqual(expected, content)

    @responses.activate
    def test_send(self):
        responses.add(
            responses.POST,
            settings.FIREBASE_API_URL,
            json.dumps({"message_id": "12345"}),
            status=200,
        )
        response = self.cms_instance.send(
            self.user, 'test:template', {"test_param": "JohnDoe"}
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    @patch('amuse.services.notifications.logger.warning')
    def test_user_no_firebase_toke(self, mock_logger):
        self.user.firebase_token = None
        self.user.save()
        self.cms_instance.send(self.user, 'test:template', {"test_param": "JohnDoe"})
        mock_logger.assert_called_once_with(
            "User.%d has no firebase_token" % (self.user.id)
        )

    @patch('amuse.services.notifications.logger.warning')
    def test_missing_template(self, mock_logger):
        self.cms_instance.send(
            self.user, 'nonexisting:template', {"test_param": "JohnDoe"}
        )
        mock_logger.assert_called_once_with(
            "Template for 'nonexisting:template' is missing"
        )

    @responses.activate
    def test_send_release_notification(self):
        responses.add(
            responses.POST,
            settings.FIREBASE_API_URL,
            json.dumps({"message_id": "12345"}),
            status=200,
        )
        release = ReleaseFactory(user=self.user)
        release_template = NotificationTemplate.objects.create(
            name='irebase:cm:release:4',
            data={
                "key": "firebase:cm:release:4",
                "body": "Hello {{ user.name }}! {{ release.name }} is approved and will now be sent to the stores! Your release will be live in stores on {{ release.release_date }}.",
                "title": "Your release is approved",
            },
        )
        response = self.cms_instance.send_release_notification(release)
        assert response is not None
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    @responses.activate
    @override_switch('service:firebase:cm:enabled', active=True)
    @patch.object(CloudMessagingService, 'send_release_notification', return_value=None)
    def test_release_notification_task_switch_on(self, mock_cms):
        release = ReleaseFactory(user=self.user)
        release_notification_task(release.id)
        mock_cms.assert_called_once_with(release)

    @override_switch('service:firebase:cm:enabled', active=False)
    @patch.object(CloudMessagingService, 'send_release_notification', return_value=None)
    def test_release_notification_task_switch_off(self, mock_cms):
        release = ReleaseFactory(user=self.user)
        release_notification_task(release.id)
        self.assertEqual(0, mock_cms.call_count)
