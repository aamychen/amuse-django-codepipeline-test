from django.core.management.base import BaseCommand
from codes.models import Code, ISRC, UPC, FAKE_UPC, FAKE_ISRC
from releases.models import Release, Song


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument(
            '--commit', help='Persist changes to DB', action='store_true', default=False
        )

        parser.add_argument(
            '--limit',
            help='Maximum releases to change before exiting',
            type=int,
            default=1,
        )

    def handle(self, *args, commit=False, limit=1, **options):
        fake_upc = self.setup_fake_upc()
        fake_isrc = self.setup_fake_isrc()

        is_candidate = self.create_candidacy_checker(upc=fake_upc, isrc=fake_isrc)

        self.stdout.write(f'Processing max {limit} releases')
        for release in Release.objects.filter(status=Release.STATUS_DELETED).iterator():
            if is_candidate(release):
                self.stdout.write(
                    f'Setting release {release} (#{release.id}) to {fake_upc}'
                )

                if commit:
                    initial_upc = release.upc
                    release.upc = fake_upc
                    release.save()
                    self.free_upc(initial_upc)

                for song in release.songs.all():
                    self.stdout.write(
                        f'Setting song {song} (#{song.id}) to {fake_isrc}'
                    )
                    if commit:
                        initial_isrc = song.isrc
                        song.isrc = fake_isrc
                        song.save()
                        self.free_isrc(initial_isrc)

                limit -= 1
                if limit <= 0:
                    self.stdout.write('Limit reached')
                    return

    def setup_fake_isrc(self):
        fake_isrc = ISRC.objects.filter(code=FAKE_ISRC).first()
        if not fake_isrc:
            fake_isrc = ISRC(code=FAKE_ISRC, status=Code.STATUS_USED)
            self.stdout.write(f'Creating fake ISRC {fake_isrc}')
            fake_isrc.save()
        return fake_isrc

    def setup_fake_upc(self):
        fake_upc = UPC.objects.filter(code=FAKE_UPC).first()
        if not fake_upc:
            fake_upc = UPC(code=FAKE_UPC, status=Code.STATUS_USED)
            self.stdout.write(f'Creating fake UPC {fake_upc}')
            fake_upc.save()
        return fake_upc

    def history_certain(self, release: Release):
        for entry in release.history.all():
            if entry.status is Release.STATUS_SUBMITTED:
                return True
            if entry.status is Release.STATUS_PENDING:
                return True
        return False

    def was_released(self, release: Release):
        for entry in release.history.all():
            if entry.status is Release.STATUS_DELIVERED:
                self.stdout.write(f'Release {release.id} was delivered')
                return True

        self.stdout.write(f'Release {release.id} was never delivered')
        return False

    def create_candidacy_checker(self, upc: UPC, isrc: ISRC):
        def is_candidate(release: Release):
            if release.upc == upc:
                return False

            if not self.history_certain(release):
                self.stdout.write(f'Release {release.id} uncertain history')
                return False

            if self.was_released(release):
                return False

            return True

        return is_candidate

    def free_upc(self, upc: UPC):
        if not Release.objects.filter(upc=upc).exists():
            upc.status = UPC.STATUS_UNUSED
            upc.save()

    def free_isrc(self, isrc: ISRC):
        if not Song.objects.filter(isrc=isrc).exists():
            isrc.status = ISRC.STATUS_UNUSED
            isrc.save()
