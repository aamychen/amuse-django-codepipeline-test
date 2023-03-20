from amuse.logging import logger
from django.db import connection


def delete_orphan_artistv2(is_test=False):
    cursor = connection.cursor()
    try:
        cursor.execute(
            "DELETE FROM users_artistv2 a "
            "WHERE owner_id IS NULL "
            "AND created < now() - interval '30 day'"
            "AND NOT EXISTS("
            "   SELECT id  "
            "   FROM users_userartistrole "
            "   WHERE artist_id = a.id) "
            "AND NOT EXISTS("
            "   SELECT id "
            "   FROM releases_songartistrole "
            "   WHERE artist_id = a.id) "
            "AND NOT EXISTS("
            "   SELECT artist_id "
            "   FROM releases_releaseartistrole "
            "   WHERE artist_id = a.id) "
            "AND NOT EXISTS("
            "   SELECT artist_id "
            "   FROM users_teaminvitation "
            "   WHERE artist_id = a.id)"
        )
        rows_deleted = cursor.rowcount
        logger.info("ArtistV2 objects deleted: %s", rows_deleted)
        if is_test:
            return rows_deleted
    except Exception as e:
        logger.error("Error removing orphan artistv2 %s", e)
    finally:
        if is_test:
            pass
        else:
            cursor.close()
            connection.close()
