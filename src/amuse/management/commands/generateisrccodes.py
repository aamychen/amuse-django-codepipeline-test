from django.core.management.base import BaseCommand
from codes.models import Code, ISRC, MANAGED_ISRC_STEMS


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument(
            '--stem', dest='stem', help='Base stem to generate codes on.'
        )
        parser.add_argument(
            '--year', dest='year', help='Two digit year to generate codes for.'
        )
        parser.add_argument(
            '--test',
            dest='test',
            action='store_true',
            help='Generate ISRC codes for testing puproses.',
        )

    def handle(self, *args, **options):
        if (options['test'] is False) and (
            options['stem'] is None or options['year'] is None
        ):
            self.stderr.write(
                "Use --test to generate test isrc for development purposes\nUse --stem and --year to generate isrc codes for production"
            )
            exit(-1)

        if options['test']:
            generate_test_isrc()
        else:
            stem = options['stem'].upper()
            year = options['year']

            if stem not in MANAGED_ISRC_STEMS:
                return self.stderr.write(f'\'{stem}\' is not a managed stem. Aborting.')

            if len(year) is not 2:
                return self.stderr.write(
                    f'\'{year}\' invalid year. Please provide a two digit value. Aborting.'
                )

            base = f'{stem}{year}'

            if ISRC.objects.filter(code__startswith=base).first():
                return self.stderr.write(
                    f'Found existing codes with base {base}. Aborting.'
                )

            ISRC.objects.bulk_create(
                [
                    ISRC(code=f'{base}{str(i).zfill(5)}', status=Code.STATUS_UNUSED)
                    for i in range(1, 100_000)
                ]
            )

            count = ISRC.objects.filter(code__startswith=base).count()
            self.stdout.write(f'Created {count} codes with base \'{base}\'')


def generate_test_isrc():
    base = "TESTX"
    ISRC.objects.bulk_create(
        [
            ISRC(code=f'{base}{str(i).zfill(5)}', status=Code.STATUS_UNUSED)
            for i in range(1, 100_000)
        ]
    )
