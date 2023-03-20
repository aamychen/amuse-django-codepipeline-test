from django.core.management.base import BaseCommand
from django.db.models import Count
from django.utils import timezone

from subscriptions.models import Subscription
from users.models import User


class Command(BaseCommand):
    def handle(self, *args, **kwargs):
        print('----------------------------------------------')
        successful_users = []
        unsuccessful_users = []
        users = (
            Subscription.objects.filter(status=Subscription.STATUS_ACTIVE)
            .values('user')
            .annotate(cnt=Count('id'))
            .filter(cnt__gte=2)
        )

        if not users.exists():
            print('No Users found with multiple active Subscriptions exiting')
        else:
            print(f'Found {len(users)} Users with multiple active Subscriptions')

        for user_data in users:
            user = User.objects.get(pk=user_data['user'])
            success, msg = self._expire_duplicate_active_subs(user)
            if success:
                successful_users.append((user.pk, msg))
            else:
                unsuccessful_users.append((user.pk, msg))
        print('----------------------------------------------')
        print(f'{len(successful_users)} users successfully fixed')
        print(successful_users)
        print('----------------------------------------------')
        print(f'{len(unsuccessful_users)} encountered an error')
        print(unsuccessful_users)
        print('----------------------------------------------')

    def _expire_duplicate_active_subs(self, user):
        try:
            subscriptions = user.subscriptions.filter(
                status=Subscription.STATUS_ACTIVE
            ).order_by('-created')
            print('----------------------------------------------')
            print(f'User {user.pk} has {subscriptions.count()} active Subscriptions')

            most_recent_sub = subscriptions.first()
            print(
                f'Keeping Subscription {most_recent_sub.pk} as the active one, expiring the rest'
            )

            subs_to_expire = subscriptions.exclude(pk=most_recent_sub.pk)
            expected_affected_rows = [sub.pk for sub in subs_to_expire.all()]
            affected_rows = subs_to_expire.update(
                valid_until=timezone.now().today(), status=Subscription.STATUS_EXPIRED
            )
            if affected_rows != len(expected_affected_rows):
                raise Exception(
                    f'Expected and updated Subscriptions mismatch - {len(expected_affected_rows)} expected, {affected_rows} updated'
                )

            return (
                True,
                f'{most_recent_sub.pk} active, {expected_affected_rows} expired',
            )
        except Exception as e:
            print(f'An error occurred while expiring Subs for User {user.pk}: {e}')
            return False, str(e)
