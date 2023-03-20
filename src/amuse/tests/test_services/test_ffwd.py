import json
from unittest.mock import patch

import responses
from django.conf import settings
from django.test import TestCase
from django.urls import reverse
from rest_framework import status

from amuse.tests.helpers import build_auth_header
from releases.models import RoyaltySplit
from releases.tests.factories import RoyaltySplitFactory


class FFWDServiceTestCase(TestCase):
    def setUp(self):
        with patch('amuse.tasks.zendesk_create_or_update_user'):
            self.split_1 = RoyaltySplitFactory(
                is_locked=True, status=RoyaltySplit.STATUS_ACTIVE
            )
            self.split_2 = RoyaltySplitFactory(
                is_locked=True,
                status=RoyaltySplit.STATUS_ACTIVE,
                user=self.split_1.user,
            )
        self.url = reverse('sns_notification')
        self.payload = {
            'Type': 'Notification',
            'TopicArn': settings.FFWD_RECOUP_SNS_TOPIC,
            'Message': json.dumps(
                {
                    "user_id": "31275",
                    "offer_id": "12345678-2220-4a8b-a42a-ef7157701edd",
                    "id": "e73e1eae-2220-4a8b-a42a-ef7157701edd",
                    "split_ids": [self.split_1.pk, self.split_2.pk],
                    "balance": 0,
                    "max_royalty_date": "2020-05-31 00:00:00 UTC",
                    "recouped_at": "2020-07-31 08:17:37 UTC",
                }
            ),
        }
        self.headers = build_auth_header(
            settings.AWS_SNS_USER, settings.AWS_SNS_PASSWORD
        )

    def test_recoup_message_unlocks_splits(self):
        self.client.post(
            self.url,
            json.dumps(self.payload),
            content_type="application/json",
            **self.headers,
        )
        self.split_1.refresh_from_db()
        self.split_2.refresh_from_db()

        assert not self.split_1.is_locked
        assert not self.split_2.is_locked


class FFWDNotificationTestCase(TestCase):
    @patch('amuse.vendor.segment.events.track')
    def test_notification_triggers_segment_event(self, mock_segment):
        url = reverse('sns_notification')
        user_id = 123
        amount = 9000.0
        offer_type = "FIRST_OFFER | LARGEST_OFFER | NEW_OFFER"
        payload = {
            'Type': 'Notification',
            'TopicArn': settings.FFWD_NOTIFICATION_SNS_TOPIC,
            'Message': json.dumps(
                {
                    "msg_type": offer_type,
                    "user_id": user_id,
                    "total_user_amount": amount,
                }
            ),
        }
        headers = build_auth_header(settings.AWS_SNS_USER, settings.AWS_SNS_PASSWORD)

        self.client.post(
            url, json.dumps(payload), content_type="application/json", **headers
        )
        mock_segment.assert_called_once_with(
            user_id,
            'ffwd_new_offer',
            properties={'amount': amount, 'type': offer_type, 'user_id': user_id},
        )
