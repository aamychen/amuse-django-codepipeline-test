from django.core.management.base import BaseCommand, CommandError
from users.models import User


class Command(BaseCommand):
    def handle(self, *args, **kwargs):
        User.objects.create_superuser(email='jimmy@amuse.io', password='password')
        User.objects.create_superuser(email='guy@amuse.io', password='password')
