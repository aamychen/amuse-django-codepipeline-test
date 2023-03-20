import logging
import pytest
from multiprocessing.dummy import Pool

from bananas.environment import env
from django.contrib.contenttypes.models import ContentType
from django.conf import settings
from django.contrib.messages import get_messages
from django.test import Client, TransactionTestCase
from django.urls import reverse

from amuse.support import count_pending_releases
from amuse.models import SupportRelease, SupportEvent
from contenttollgate.utils import generate_presigned_post
from releases.models import Release
from releases.tests.factories import ReleaseFactory
from subscriptions.models import SubscriptionPlan
from users.models import User
from users.tests.factories import UserFactory


class AdminContentTollgateTestCase(TransactionTestCase):
    def setUp(self):
        ContentType.objects.clear_cache()
        settings.AWS_REGION = 'placeholder'

        # Set tests specific log level and limit to console handler
        settings.LOGGING['disable_existing_loggers'] = True
        for logger in settings.LOGGING.get('loggers', {}).values():
            logger['level'] = env.get('DJANGO_LOG_LEVEL_TESTS', 'CRITICAL')
            logger['handlers'] = ['console']
        logging.config.dictConfig(settings.LOGGING)

    @pytest.mark.skip
    def test_tollgate_concurrent(self):
        url = reverse('admin:assign_pending_releases')
        POOL_SIZE = 3
        pool = Pool(POOL_SIZE)
        users = [UserFactory(is_staff=True) for _ in range(POOL_SIZE)]
        releases = [ReleaseFactory(status=Release.STATUS_PENDING) for _ in range(30)]

        def concurrent_release_assigns(user):
            client = Client()
            client.login(email=user.email, password='hunter2')
            response = client.get(url)
            all_messages = [m.message for m in get_messages(response.wsgi_request)]
            return all_messages[0]

        messages = pool.map(concurrent_release_assigns, users)
        pool.close()
        pool.join()

        support_releases = SupportRelease.objects.all()
        support_events = SupportEvent.objects.all()
        self.assertEqual(support_releases.count(), 10)
        self.assertEqual(support_releases.count(), support_events.count())

        self.assertIn('Please try again', messages)
        self.assertIn('You were assigned 10 releases', messages)

    def test_generate_presigned_post(self):
        bucket = "foo"
        key = "bar"

        result = generate_presigned_post(bucket, key)

        assert result["url"]
        assert result["fields"]["key"]
        assert result["fields"]["AWSAccessKeyId"]
        assert result["fields"]["policy"]
        assert result["fields"]["signature"]

    def test_count_pending_releases(self):
        user0 = UserFactory(is_pro=True)
        user1 = UserFactory(is_pro=False)

        ReleaseFactory(created_by=user0, status=Release.STATUS_PENDING)
        ReleaseFactory(created_by=user0, status=Release.STATUS_PENDING)
        ReleaseFactory(created_by=user1, status=Release.STATUS_PENDING)

        assert count_pending_releases(SubscriptionPlan.TIER_PRO) == 2
        assert count_pending_releases(User.TIER_FREE) == 1
