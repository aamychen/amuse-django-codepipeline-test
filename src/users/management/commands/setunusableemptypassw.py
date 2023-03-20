from django.core.management.base import BaseCommand
from django.db.models import Q
from django.db.models.functions import Concat
from django.db.models import Value as V
from django.utils.crypto import get_random_string
from users.models import User


class Command(BaseCommand):
    def handle(self, *args, **kwargs):
        empty_pass_users = User.objects.filter(Q(password=None) | Q(password=''))
        empty_pass_users.update(password=Concat(V('!'), V(get_random_string(40))))
