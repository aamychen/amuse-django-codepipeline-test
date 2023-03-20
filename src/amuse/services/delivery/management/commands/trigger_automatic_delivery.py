import logging

from datetime import timedelta
from uuid import uuid4

from django.core.management.base import BaseCommand
from django.utils import timezone

from amuse.services.delivery.helpers import deliver_batches, get_non_delivered_dd_stores
from releases.models import Release
from releases.utils import filter_release_error_flags, filter_songs_error_flags
from users.models import User


logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = """
    This command is used to process a subset of releases and check if they have stores
    that have not been delivered to and trigger DD deliveries for them.

    Running it with `--status approved` is straight forward as no existing deliveries
    should be found on the releases.

    Running it with `--status delivered` selects releases that have status approved and
    released. This comes with more complexity as already delivered releases can be in
    many different states so you need to be aware of the different types and how they
    should be handled.

    Please make sure that you are aware of how deliveries to bundled stores like
    Amazon/Twitch, FB/IG works before running this command. You can specify `--stores`
    explicitly to skip bundled stores if needed.

    The bdr_id range you can specify is basically being able to tell the command to
    `Process only releases that has deliveries between X and Y`.

    It is recommended to run the command with `--dryrun` first and check the output so
    you understand exactly how the releases will be processed.
    """

    def add_arguments(self, parser):
        parser.add_argument(
            "--status",
            type=str,
            help="Release status. Supported values are `approved` and `delivered`. `delivered` picks both Delivered and Released releases.",
        )
        parser.add_argument(
            "--stores",
            type=str,
            nargs="+",
            default=None,
            help="Only process these space-separated store internal_names",
        )
        parser.add_argument(
            "--bdr_id_start",
            type=int,
            help="Process releases starting with BatchDeliveryRelease.id in this range",
        )
        parser.add_argument(
            "--bdr_id_end",
            type=int,
            help="Process releases ending with BatchDeliveryRelease.id in this range",
        )
        parser.add_argument(
            "--limit", type=int, default=100, help="How many releases to process"
        )
        parser.add_argument(
            "--batchsize",
            type=int,
            default=10,
            help="How many releases to include in a batch",
        )
        parser.add_argument(
            "--delay", type=float, default=5, help="Delay between triggering each batch"
        )
        parser.add_argument(
            "--fuga_delay",
            type=float,
            default=0.5,
            help="Delay between triggering each Fuga API call",
        )
        parser.add_argument(
            "--dryrun",
            action="store_true",
            default=False,
            help="Only print what will be processed",
        )
        parser.add_argument(
            "--user_id",
            type=int,
            default=None,
            help="Specify the ID of the user who is triggering this automatic delivery",
        )
        parser.add_argument(
            "--days",
            type=int,
            default=1,
            help="Specify how many days to process. Checks Release.updated. 1 is current day. 0 is no limit.",
        )
        parser.add_argument(
            "--agent_ids",
            type=int,
            nargs="+",
            help="Only process releases approved by these space-separated user_ids.",
        )

    def handle(self, *args, **kwargs):
        start_time = timezone.now()
        status = kwargs["status"]
        stores = kwargs["stores"]
        bdr_id_start = kwargs["bdr_id_start"]
        bdr_id_end = kwargs["bdr_id_end"]
        batchsize = kwargs["batchsize"]
        limit = kwargs["limit"]
        delay = kwargs["delay"]
        fuga_delay = kwargs["fuga_delay"]
        dryrun = kwargs["dryrun"]
        user_id = kwargs["user_id"]
        days = kwargs["days"]
        agent_ids = kwargs["agent_ids"]

        job_id = "Automatic delivery job [%s] %s:" % (status, str(uuid4()))

        logger.info("%s settings %s" % (job_id, kwargs))

        if status == "approved":
            release_status = [Release.STATUS_APPROVED]
        elif status == "delivered":
            release_status = [Release.STATUS_DELIVERED, Release.STATUS_RELEASED]
        else:
            logger.error("%s Unsupported status type" % job_id)
            return

        filter_kwargs = self.build_query(
            status,
            release_status,
            start_time,
            bdr_id_start,
            bdr_id_end,
            days,
            agent_ids,
        )

        releases = (
            Release.objects.filter(**filter_kwargs)
            .distinct()
            .order_by("updated")[:limit]
        )

        releases = self.remove_unallowed_error_flags(job_id, releases)

        logger.info(
            "%s Found releases %s with status %s to check non-delivered DD stores"
            % (job_id, [r.pk for r in releases], status)
        )

        stores_releases = get_non_delivered_dd_stores(releases, stores)
        results = self.process_releases(
            user_id, stores_releases, batchsize, delay, dryrun
        )

        logger.info(
            "%s Done for %s. Time to process: %s"
            % (job_id, results, (timezone.now() - start_time))
        )

    def remove_unallowed_error_flags(self, job_id, releases):
        """
        We only allow releases/tracks to have the following error flags or none.

        - Release.error_flags.metadata_symbols-emoji-info (19)
        - Song.error_flags.explicit_lyrics (4)

        We can't do this on SQL level due to this:
        https://github.com/disqus/django-bitfield/issues/89
        """
        results = []
        filtered_releases = filter_release_error_flags(releases, job_id)

        for release in filtered_releases:
            songs = release.songs.all()
            filtered_songs = filter_songs_error_flags(songs, job_id)

            if len(filtered_songs) == songs.count():
                results.append(release)

        return results

    def build_query(
        self,
        status,
        release_status,
        start_time,
        bdr_id_start,
        bdr_id_end,
        days,
        agent_ids,
    ):
        filter_kwargs = {"status__in": release_status}

        if days > 0:
            today = start_time
            start_date = (today - timedelta(days=days - 1)).replace(
                hour=0, minute=0, second=0, microsecond=0
            )
            end_date = today.replace(hour=23, minute=59, second=59, microsecond=999999)
            filter_kwargs["updated__range"] = [
                start_date.isoformat(),
                end_date.isoformat(),
            ]

        if status == "delivered" and bdr_id_start and bdr_id_end:
            filter_kwargs["batchdeliveryrelease__id__range"] = [
                bdr_id_start,
                bdr_id_end,
            ]

        if status == "approved" and agent_ids:
            filter_kwargs["supportrelease__assignee__pk__in"] = agent_ids

        return filter_kwargs

    def process_releases(self, user_id, stores_releases, batchsize, delay, dryrun):
        user = User.objects.get(id=user_id) if user_id else None
        results = []

        for store, releases in stores_releases.items():
            uniq_releases = list(set(releases))
            uniq_releases.sort(key=lambda x: x.updated)
            uniq_releases_ids = [r.pk for r in uniq_releases]

            store_delivery_message = "Deliver releases %s to store %s" % (
                uniq_releases_ids,
                store,
            )
            results.append(store_delivery_message)

            deliver_batches(
                releases=uniq_releases,
                delivery_type="insert",
                override_stores=False,
                stores=[store],
                batchsize=batchsize,
                delay=delay,
                dryrun=dryrun,
                user=user,
            )

        return results
