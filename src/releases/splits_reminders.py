from amuse.logging import logger
from django.db import connection
from amuse.utils import MapPgResults
from amuse.vendor.customerio.events import default as cioevents


def send_split_not_accepted_3_days(is_test=False):
    cursor = connection.cursor()
    try:
        cursor.execute(
            "select rsp.rate, ri.email as recipient, ri.phone_number, ri.name as invitee_name, "
            "ri.token, rs.name as song_name, uu.first_name, uu.last_name, rr.release_date "
            "from releases_royaltysplit rsp "
            "join users_royaltyinvitation ri on ri.royalty_split_id = rsp.id "
            "join users_user uu on uu.id = ri.inviter_id "
            "join releases_song rs on rs.id = rsp.song_id "
            "join releases_release rr on rr.id=rs.release_id "
            "where ri.status = 2 and  "
            "rsp.user_id is null and "
            "ri.created between now() - interval '3 day' and now() - interval '2 day'"
        )
        results = cursor.fetchall()
        data = [MapPgResults(cursor, r) for r in results]
        if is_test:
            return data
        for d in data:
            logger.info("Sending 3 day split reminder to recipient=%s" % d.recipient)
            cioevents().send_split_3_day_reminder(inputdata=d)

    except Exception as e:
        logger.error("Error sending split_not_accepted_3_days reminders  %s", e)
    finally:
        if is_test:
            pass
        else:
            cursor.close()
            connection.close()


def send_split_day_before_release(is_test=False):
    cursor = connection.cursor()
    try:
        cursor.execute(
            "select rsp.rate, ri.email as recipient, ri.phone_number, ri.name as invitee_name, "
            "ri.token, rs.name as song_name, uu.first_name, uu.last_name, rr.release_date "
            "from releases_royaltysplit rsp "
            "join users_royaltyinvitation ri on ri.royalty_split_id = rsp.id "
            "join users_user uu on uu.id = ri.inviter_id "
            "join releases_song rs on rs.id = rsp.song_id "
            "join releases_release rr on rr.id=rs.release_id "
            "where ri.status = 2 and  "
            "rsp.user_id is null and "
            "rr.release_date between now() and now()+ interval '1 day' "
        )
        results = cursor.fetchall()
        data = [MapPgResults(cursor, r) for r in results]
        if is_test:
            return data
        for d in data:
            logger.info(
                "Sending 1 day before release split reminder to recipient=%s"
                % d.recipient
            )
            e = cioevents()
            e.send_day_before_release_reminder(inputdata=d)

    except Exception as e:
        logger.error(
            "Error sending split_not_accepted_day_before_release reminders %s", e
        )
    finally:
        if is_test:
            pass
        else:
            cursor.close()
            connection.close()
