from uuid import uuid4
from django.core.management.base import BaseCommand, CommandError
from codes.models import ISRC, UPC


class Command(BaseCommand):
    def handle(self, *args, **options):
        for i in range(0, 1000):
            ISRC.objects.create(code='XX%03d%07d' % (i, i))
            UPC.objects.create(code='TEST%s' % str(uuid4().hex)[:8].upper())
