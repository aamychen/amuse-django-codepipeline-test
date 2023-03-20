from django.core.management import BaseCommand
from django.db import connection
from amuse.vendor.acrcloud.id import identify_song
from releases.models.song import Song


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument('--order', dest='order', default='asc')
        parser.add_argument('--limit', dest='limit', type=int, default=1000)

    def handle(self, *args, **options):
        with connection.cursor() as cur:
            order = 'DESC' if options['order'] == 'desc' else 'ASC'
            limit = int(options['limit'])
            cur.execute(
                f'SELECT id, code FROM fuga_codes WHERE status = 0 ORDER BY id {order} LIMIT {limit}'
            )
            for row in cur.fetchall():
                print(row)
                for song in Song.objects.filter(release__upc__code=row[1]):
                    if song.acrcloud_matches.count():
                        cur.execute(
                            'UPDATE fuga_codes SET status = 1 WHERE id = %s', [row[0]]
                        )
                        print(
                            f'{song.release.upc}/{song.id} has an ACRCloudMatch relation, skipping.'
                        )
                        continue

                    try:
                        identify_song(song)
                        print(f'{row[0]}: {song.release.upc}/{song.isrc}')
                    except Exception as e:
                        print(f'{song.release.upc}/{song.id} failed with {str(e)}')
                cur.execute('UPDATE fuga_codes SET status = 1 WHERE id = %s', [row[0]])
