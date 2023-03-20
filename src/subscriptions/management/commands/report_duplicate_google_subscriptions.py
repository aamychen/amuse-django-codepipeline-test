import logging

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db.models import Count

from amuse.vendor.customerio import events as cio
from subscriptions.models import Subscription

logger = logging.getLogger('report_duplicate_google_subscriptions')


class Command(BaseCommand):
    def handle(self, *args, **kwargs):
        send_to = settings.REPORT_DUPLICATE_GOOGLE_SUBSCRIPTIONS_TO
        if not send_to:
            logger.warning('Email not set. No duplicate Google subscriptions.')
            return

        counts = (
            Subscription.objects.filter(
                status__in=(
                    Subscription.STATUS_ACTIVE,
                    Subscription.STATUS_GRACE_PERIOD,
                )
            )
            .values('user_id')
            .annotate(cnt=Count('id'))
            .filter(cnt__gte=2, provider=Subscription.PROVIDER_GOOGLE)
        )

        user_ids = [item['user_id'] for item in counts]

        subscriptions = (
            Subscription.objects.filter(
                user_id__in=user_ids,
                status__in=[
                    Subscription.STATUS_ACTIVE,
                    Subscription.STATUS_GRACE_PERIOD,
                ],
            )
            .order_by('user_id', 'id')
            .values('user_id', 'id', 'created')
        )

        logger.info(f'Duplicate Google subscriptions found: {len(subscriptions)}')
        send = len(subscriptions) > 0
        if not send:
            logger.info('Email not sent. Nothing to report.')
            return

        payload = {
            'subscriptions': [
                {
                    'user_id': sub['user_id'],
                    'subscription_id': sub['id'],
                    'created': str(sub['created']),
                }
                for sub in subscriptions
            ]
        }

        cio.default().report_duplicate_google_subscriptions(
            recipient=send_to, data=payload
        )
