from django.core.management.base import BaseCommand
from users.models import TeamInvitation
from datetime import datetime, timedelta


class Command(BaseCommand):
    def handle(self, *args, **kwargs):
        time_threshold = datetime.now() - timedelta(days=TeamInvitation.EXPIRATION_DAYS)
        TeamInvitation.objects.filter(
            last_sent__lt=time_threshold, status=TeamInvitation.STATUS_PENDING
        ).update(status=TeamInvitation.STATUS_EXPIRED)
