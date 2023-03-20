from django.core.management.base import BaseCommand
from django.db import connection, DatabaseError, transaction


class Command(BaseCommand):
    help = """
        Sets main_primary_artist=True to selected ReleaseArtistRoles
        """

    def handle(self, *args, **kwargs):
        try:
            command = """
                WITH subquery AS (
                    SELECT DISTINCT ON (rar.release_id) rar.id
                    FROM releases_releaseartistrole rar
                    WHERE rar.role = 1
                    ORDER BY rar.release_id, rar.id ASC
                )
                    UPDATE releases_releaseartistrole rar
                    SET main_primary_artist = true
                    FROM subquery
                    WHERE rar.id = subquery.id;
            """

            with connection.cursor() as cursor:
                self.stdout.write(f'Updating ReleaseArtistRoles')
                cursor.execute(command)
                self.stdout.write(f'Finished updating ReleaseArtistRoles')
        except DatabaseError as e:
            self.stderr.write(f'Database Error: {e}')
            self.stderr.write(f'Performing a rollback')
            transaction.rollback()
        except Exception as e:
            self.stderr.write(f'Error: {e}')
