import os
import binascii

from django.core.management.base import BaseCommand
from rest_framework.authtoken.models import Token
from datetime import datetime

from users.models import User


class Command(BaseCommand):
    help = f"Command for reinstating access after user requested account delete. This command will create token which was previously removed and remove is_delete_requested flag."

    def add_arguments(self, parser):
        parser.add_argument(
            "--user-id",
            nargs='+',
            type=int,
            help='Single/multiple user ids separated by space. Example: 1 2 3 4',
        )
        parser.add_argument(
            "--dry-run",
            dest="dry_run",
            action="store_true",
            default=False,
            help="Only print results and doesn't write to database",
        )

    def handle(self, *args, **options):
        user_ids = options.get("user_id")
        is_dry_run = options.get("dry_run")

        users = User.objects.filter(pk__in=user_ids)

        for user in users:
            # Create auth token
            new_token_key = binascii.hexlify(os.urandom(20)).decode()

            self.stdout.write(
                f"New token {new_token_key} will be created for the user with ID {user.id}"
            )
            if not is_dry_run:
                Token.objects.update_or_create(
                    user=user,
                    defaults={'key': new_token_key, 'created': datetime.now()},
                )
                self.stdout.write(self.style.SUCCESS(f"New token saved"))

                user.usermetadata.is_delete_requested = False
                user.usermetadata.delete_requested_at = None
                user.usermetadata.save()

        self.stdout.write("Done!")
