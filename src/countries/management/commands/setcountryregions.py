from django.core.management.base import BaseCommand

from countries.management.regions import REGIONS
from countries.models import Country


class Command(BaseCommand):
    help = 'Populate countries with the region code'

    def handle(self, *args, **options):
        for region in REGIONS:
            region_code = region['region_code']
            count = Country.objects.filter(code__in=region['country_codes']).update(
                region_code=region_code
            )
            self.stdout.write(
                f'Updated {count} countries with region code {region_code}'
            )
