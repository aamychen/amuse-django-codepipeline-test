from queue import Queue
import threading
from amuse.logging import logger
from threading import Thread
from django.core.management.base import BaseCommand
from django.db import connection
import sys
from releases.models import Release, Song


class Command(BaseCommand):
    help = (
        'Update artist_sequence in rar and sar tables'
        'Usage: python manage.py updateartistsequence --confirm=yes'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--confirm', help='Confirm execution', required=True, type=str
        )
        parser.add_argument(
            '--to_release_id',
            help="Update all releases data with id less then this value",
            type=int,
        )

        parser.add_argument(
            '--only_rar',
            help="Update only releases_releaseartistrole",
            type=bool,
            default=False,
        )

        parser.add_argument(
            '--only_sar',
            help="Update only releases_songartistrole",
            type=bool,
            default=False,
        )

        parser.add_argument(
            '--threads',
            help="Number of threads",
            type=int,
            default=10,
        )

        parser.add_argument(
            '--test_mode',
            help="For unit test",
            type=bool,
            default=False,
        )

    def handle(self, *args, **kwargs):
        if kwargs['confirm'] not in ['yes', 'YES']:
            logger.info("Skipping migrations. Confirm argument must be yes|YES")
            sys.exit(-1)
        limit = kwargs['to_release_id']
        only_rar = kwargs['only_rar']
        only_sar = kwargs['only_sar']
        threads = kwargs['threads']
        test_mode = kwargs['test_mode']
        queue = Queue()
        if test_mode:
            update_rar()
            queue, total = add_songs_to_queue(queue)
            update_sar_artist_sequence(queue=queue, total=total, test=True)
            return

        if only_rar:
            if limit:
                update_rar(to_release_id=limit)
                return
            else:
                update_rar()
                return
        if only_sar:
            if limit:
                queue, total = add_songs_to_queue(queue, to_release_id=limit)
            else:
                queue, total = add_songs_to_queue(queue)
            for i in range(threads):
                worker = Thread(target=update_sar_artist_sequence, args=(queue, total))
                worker.setDaemon(True)
                worker.start()
            queue.join()
            return
        if limit:
            update_rar(to_release_id=limit)
            queue, total = add_songs_to_queue(queue, to_release_id=limit)
            for i in range(threads):
                worker = Thread(target=update_sar_artist_sequence, args=(queue, total))
                worker.setDaemon(True)
                worker.start()
            queue.join()
            return

        update_rar()
        queue, total = add_songs_to_queue(queue)
        for i in range(threads):
            worker = Thread(target=update_sar_artist_sequence, args=(queue, total))
            worker.setDaemon(True)
            worker.start()
        queue.join()


def update_sar_artist_sequence(queue, total, test=False):
    logger.info("Starting thread= %s", threading.current_thread().name)
    while True:
        try:
            progress = queue.qsize()
            if test and progress == 0:
                break
            percents_done = (1.0 - (progress) / total) * 100
            if progress % 10000 == 0:
                logger.info(
                    " %s - %s  [%s]%% ",
                    threading.current_thread().name,
                    progress,
                    round(percents_done),
                )
            song_id = queue.get()
            song = Song.objects.get(id=song_id)
            sar_qs = song.songartistrole_set.all().order_by('role', 'created')
            start = 1
            for sar in sar_qs:
                sar.artist_sequence = start
                sar.save()
                start += 1
            queue.task_done()
        except Exception as e:
            logger.exception("Error updating releases_releaseartistrole table")
            queue.task_done()


def update_rar(to_release_id=sys.maxsize):
    try:
        logger.info("Updating artist_sequence in rar")
        cursor = connection.cursor()
        cursor.execute(
            "update releases_releaseartistrole set artist_sequence=1 where role =1 "
            "and release_id < %s",
            [to_release_id],
        )
        cursor.execute(
            "update releases_releaseartistrole set artist_sequence=2 where role =2 "
            "and release_id < %s",
            [to_release_id],
        )
        logger.info("Done")
    except Exception as e:
        logger.exception("Error updating releases_releaseartistrole table")
    finally:
        cursor.close()


def add_songs_to_queue(queue, to_release_id=sys.maxsize):
    try:
        cursor = connection.cursor()
        cursor.execute(
            "select rs.id from releases_song rs  join releases_release rr "
            "on rs.release_id=rr.id where rr.status not in (%s,%s,%s)",
            [
                Release.STATUS_DELETED,
                Release.STATUS_REJECTED,
                Release.STATUS_NOT_APPROVED,
            ],
        )
        song_ids = cursor.fetchall()
        total = len(song_ids)
        for song_id in song_ids:
            queue.put(song_id[0])
        return queue, total

    except Exception as e:
        logger.exception("Error migrating Artist -> ArtistV2")

    finally:
        cursor.close()
