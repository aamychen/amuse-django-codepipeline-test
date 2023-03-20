from django.core.management.base import BaseCommand

from users.gdpr import clean_user_data
from users.models import User, UserGDPR


class Command(BaseCommand):
    help = 'Delete remaining data from GDPR incompete user wipe out.'

    def handle(self, *args, **options):
        deleted_users_ids = UserGDPR.objects.all().values_list('user_id')
        users = User.objects.filter(id__in=deleted_users_ids)

        for user in users:
            clean_user_data(user.id)
            self.stdout.write(
                f'Remaining data for user {user.id} was cleaned successfully.'
            )
