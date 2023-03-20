from django.conf import settings
from django.core.management import BaseCommand

from amuse.vendor.adyen.helpers import get_adyen_client


ADYEN_DOMAINS = {
    'https://artist-staging.amuse.io': 'vue',
    'https://artist-staging-pro.amuse.io': 'vue 2',
    'https://app-staging.amuse.io': 'staging-django-setting',
    'http://app-dev.amuse.io': 'development-django-setting',
}


class Command(BaseCommand):
    def handle(self, *args, **options):
        if settings.ADYEN_PLATFORM != 'test':
            print('Only for dev/staging environment')
            exit(1)

        client = get_adyen_client()

        response = client.checkout.origin_keys(
            {'originDomains': list(ADYEN_DOMAINS.keys())}
        )
        origin_keys = response.message['originKeys']

        for origin_domain, environment in ADYEN_DOMAINS.items():
            key = origin_keys[origin_domain]
            print(f'{environment} ({origin_domain}): {key}')
