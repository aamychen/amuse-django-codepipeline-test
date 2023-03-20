from django.test import TestCase
from django.test.utils import override_settings
from unittest.mock import patch

from amuse.tests.helpers import ZENDESK_MOCK_API_URL_TOKEN
from users.tests.factories import UserFactory
from amuse.vendor.zendesk.cron import backfill_zendesk_id
from users.models import User


@override_settings(**ZENDESK_MOCK_API_URL_TOKEN)
class TestZendeskBackfillCron(TestCase):
    @staticmethod
    def prepare_data():
        test_data = list()
        for i in range(1, 5):
            user = UserFactory()
            test_data.append({'external_id': user.id, 'id': int(user.id) + 1000})
        return test_data

    @patch('amuse.tasks.zendesk_create_or_update_user')
    def test_backfill_zendesk_id(self, mock_task):
        test_data = self.prepare_data()
        backfill_zendesk_id(test_data)
        for item in test_data:
            user = User.objects.get(id=item['external_id'])
            self.assertEqual(user.zendesk_id, int(user.id) + 1000)
