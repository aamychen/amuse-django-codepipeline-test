from datetime import datetime

from django.core.management.base import BaseCommand

from amuse.mails import send_security_update_mail
from users.models import User, Comments

DATE_FORMAT = '%Y-%m-%d'


def change_password_and_send_email(user):
    user.set_unusable_password()

    if hasattr(user, 'comments'):
        comment = user.comments
    else:
        comment = Comments(user=user, text='')

    reset_comment = f'{datetime.now().strftime(DATE_FORMAT)}: Automatic password reset and user notified by email'
    comment.text = f'{reset_comment}\r\n\r\n{comment.text}'

    user.save()
    comment.save()

    send_security_update_mail(user)


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument(
            '--ids', nargs='+', help='User IDs', required=True, dest='user_ids'
        )

    def handle(self, *args, user_ids=None, **kwargs):
        for user_id in user_ids:
            self.force_change_for_user_with_usable_password(user_id)

    def force_change_for_user_with_usable_password(self, user_id):
        user = User.objects.filter(pk=int(user_id)).first()
        if not user:
            self.stdout.write(f'User {user_id} does not exist')
            return

        if not user.has_usable_password():
            self.stdout.write(f'User {user_id} already has unusable password')
            return

        change_password_and_send_email(user)
