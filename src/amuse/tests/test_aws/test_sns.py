import json
from unittest import mock

import responses
from django.conf import settings
from django.test import TransactionTestCase
from django.urls import reverse_lazy as reverse
from requests.exceptions import HTTPError
from waffle.models import Switch

from amuse.models.deliveries import BatchDelivery
from amuse.tests.factories import BatchDeliveryFactory, BatchDeliveryReleaseFactory
from amuse.tests.helpers import build_auth_header
from releases.tests.factories import ReleaseFactory


class SNSTestCase(TransactionTestCase):
    def setUp(self):
        self.headers = build_auth_header(
            settings.AWS_SNS_USER, settings.AWS_SNS_PASSWORD
        )
        self.url = reverse("sns_notification")

    def test_no_json_request(self):
        response = self.client.post(self.url, {"foo": "bar"}, **self.headers)
        assert response.status_code == 400

    def test_bad_json_request(self):
        response = self.client.post(
            self.url, '{"foo": "bar}', content_type="application/json", **self.headers
        )
        assert response.status_code == 400

    @responses.activate
    def test_subscription_confirmation_error(self):
        notification = {
            "Type": "SubscriptionConfirmation",
            "SubscribeURL": "http://example.com/sns",
        }
        responses.add(responses.GET, notification["SubscribeURL"], status=404)
        with self.assertRaises(HTTPError):
            self.client.post(
                self.url,
                json.dumps(notification),
                content_type="application/json",
                **self.headers,
            )

    @responses.activate
    def test_subscription_confirmation_success(self):
        notification = {
            "Type": "SubscriptionConfirmation",
            "SubscribeURL": "http://example.com/sns",
        }
        responses.add(responses.GET, notification["SubscribeURL"], status=200)
        response = self.client.post(
            self.url,
            json.dumps(notification),
            content_type="application/json",
            **self.headers,
        )
        assert response.status_code == 200

    def test_invalid_topic_404(self):
        notification = {
            "Type": "Notification",
            "TopicArn": "invalid-topic",
            "Message": json.dumps({"foo": "bar"}),
        }
        response = self.client.post(
            self.url,
            json.dumps(notification),
            content_type="application/json",
            **self.headers,
        )
        assert response.status_code == 404

    def test_ffwd_recoup_invalid_http_auth_returns_401_if_switch_is_active(self):
        Switch.objects.create(name='sns:require_ffwd_recoup_auth', active=True)
        response = self.client.post(
            self.url,
            json.dumps(
                {
                    'Type': 'Notification',
                    'TopicArn': settings.FFWD_RECOUP_SNS_TOPIC,
                    'Message': json.dumps({'split_ids': [1]}),
                }
            ),
            content_type='application/json',
            **build_auth_header('h4x0r', 'k1dd13'),
        )

        self.assertEqual(response.status_code, 401)

    def test_ffwd_recoup_valid_http_auth_returns_200_if_switch_is_active(self):
        Switch.objects.create(name='sns:require_ffwd_recoup_auth', active=True)
        response = self.client.post(
            self.url,
            json.dumps(
                {
                    'Type': 'Notification',
                    'TopicArn': settings.FFWD_RECOUP_SNS_TOPIC,
                    'Message': json.dumps({'split_ids': [1]}),
                }
            ),
            content_type='application/json',
            **self.headers,
        )

        self.assertEqual(response.status_code, 200)

    def test_ffwd_recoup_no_http_auth_returns_200_if_switch_is_not_active(self):
        Switch.objects.create(name='sns:require_ffwd_recoup_auth', active=False)
        response = self.client.post(
            self.url,
            json.dumps(
                {
                    'Type': 'Notification',
                    'TopicArn': settings.FFWD_RECOUP_SNS_TOPIC,
                    'Message': json.dumps({'split_ids': [1]}),
                }
            ),
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 200)

    def test_smart_link_callback_authenticated(self):
        mock_releases = ReleaseFactory.create_batch(size=20)
        mock_msg_batch = [
            {
                'type': 'track',
                'amuse_release_id': mock_release.id,
                'link': f'https://share.amuse.io/track/{mock_release.id}',
            }
            for mock_release in mock_releases
        ]
        response = self.client.post(
            self.url,
            json.dumps(
                {
                    'Type': 'Notification',
                    'TopicArn': settings.SMART_LINK_CALLBACK_SNS_TOPIC,
                    'Message': json.dumps(mock_msg_batch),
                }
            ),
            content_type='application/json',
            **self.headers,
        )
        self.assertEqual(response.status_code, 200)
        for mock_release in mock_releases:
            mock_release.refresh_from_db()
            mock_link = f'https://share.amuse.io/track/{mock_release.id}'
            self.assertEqual(mock_release.link, mock_link)

    @mock.patch('amuse.services.smart_link.amuse_smart_link_callback')
    def test_smart_link_callback_not_authenticated(
        self, amuse_smart_link_callback_mock
    ):
        message = [
            {
                'type': 'track',
                'amuse_release_id': 123456789,
                'link': 'https://share.amuse.io/track/test-track',
            }
        ]
        response = self.client.post(
            self.url,
            json.dumps(
                {
                    'Type': 'Notification',
                    'TopicArn': settings.SMART_LINK_CALLBACK_SNS_TOPIC,
                    'Message': json.dumps(message),
                }
            ),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 401)
        amuse_smart_link_callback_mock.assert_not_called()

    @mock.patch('amuse.tasks.zendesk_create_or_update_user')
    @mock.patch('amuse.services.delivery.callback._update_release_status')
    def test_delivery_callback_return_200_when_object_exists(
        self, mock_update, mock_zen
    ):
        release = ReleaseFactory()
        delivery = BatchDeliveryFactory(
            status=BatchDelivery.STATUS_SUCCEEDED, channel=1
        )
        BatchDeliveryReleaseFactory(release=release, delivery=delivery)

        response = self.client.post(
            self.url,
            json.dumps(
                {
                    'Type': 'Notification',
                    'TopicArn': settings.RELEASE_DELIVERY_SERVICE_RESPONSE_TOPIC,
                    'Message': json.dumps(
                        {
                            'delivery_id': delivery.delivery_id,
                            'type': 'delivery_update',
                            'status': 'delivered',
                            'releases': {
                                release.pk: {'status': 'delivered', 'errors': []}
                            },
                        }
                    ),
                }
            ),
            content_type='application/json',
            **self.headers,
        )

        self.assertEqual(response.status_code, 200)

    def test_delivery_callback_return_500_when_object_does_not_exist(self):
        response = self.client.post(
            self.url,
            json.dumps(
                {
                    'Type': 'Notification',
                    'TopicArn': settings.RELEASE_DELIVERY_SERVICE_RESPONSE_TOPIC,
                    'Message': json.dumps(
                        {'delivery_id': 1, 'type': 'delivery_update'}
                    ),
                }
            ),
            content_type='application/json',
            **self.headers,
        )

        self.assertEqual(response.status_code, 500)
