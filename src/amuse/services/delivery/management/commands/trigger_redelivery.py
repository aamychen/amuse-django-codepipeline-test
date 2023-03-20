from collections import defaultdict
import logging
from datetime import datetime

from django.core.management.base import BaseCommand
from django.db.models import Q

from amuse.deliveries import CHANNELS, FUGA
from amuse.models.deliveries import BatchDeliveryRelease
from amuse.services.delivery.helpers import deliver_batches
from releases.models import Release
from users.models import User

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument(
            "--bdr_id_start",
            type=int,
            help="Process releases starting with BatchDeliveryRelease.id in this range that are marked for redelivery",
        )
        parser.add_argument(
            "--bdr_id_end",
            type=int,
            help="Process releases ending with BatchDeliveryRelease.id in this range that are marked for redelivery",
        )
        parser.add_argument(
            "--batchsize",
            type=int,
            default=10,
            help="Specify how many releases to include in a batch",
        )
        parser.add_argument(
            "--delay",
            type=float,
            default=5,
            help="Specify delay between triggering each batch",
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
            help="Specify the ID of the user who is triggering this re-delivery",
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=100,
            help="Specify number of releases to run for",
        )

    def handle(self, *args, **kwargs):
        start_time = datetime.now()

        bdr_id_start = kwargs["bdr_id_start"]
        bdr_id_end = kwargs["bdr_id_end"]
        batchsize = kwargs["batchsize"]
        delay = kwargs["delay"]
        dryrun = kwargs["dryrun"]
        user_id = kwargs["user_id"]
        limit = kwargs['limit']

        bdrs_by_channel_and_type = self.get_bdrs_by_channel_and_type(
            bdr_id_start, bdr_id_end, limit
        )

        if len(bdrs_by_channel_and_type) == 0:
            nope_message = "No redeliveries found"
            self.stdout.write(nope_message)
            return nope_message
        else:
            logging.info(
                f"Running redeliveries for {len(bdrs_by_channel_and_type)} batch delivery releases"
            )

        if dryrun:
            print(
                "BDR by channel and type:\n",
                {k: dict(v) for k, v in dict(bdrs_by_channel_and_type).items()},
                "\n",
            )

        user = None

        if user_id:
            user = User.objects.get(id=user_id)

        kwargs = {
            "batchsize": batchsize,
            "delay": delay,
            "dryrun": dryrun,
            "user": user,
        }
        bdr_ids = []

        for channel, data in bdrs_by_channel_and_type.items():
            if channel == FUGA:
                kwargs["only_fuga"] = True
            else:
                channel_string = [v for k, v in CHANNELS.items() if k == channel][0]
                kwargs["stores"] = [channel_string]

            for delivery_type, bdr_list in data.items():
                kwargs["delivery_type"] = delivery_type

                # Can only do single batches for Fuga as stores differs on
                # release-level
                if channel == FUGA:
                    for bdr in bdr_list:
                        kwargs["releases"] = [bdr.release]
                        deliver_batches(**kwargs)

                        if not dryrun:
                            bdr.redeliver = False
                            bdr.status = BatchDeliveryRelease.STATUS_REDELIVERED
                            bdr.save()
                else:
                    releases = Release.objects.filter(
                        pk__in=[bdr.release_id for bdr in bdr_list]
                    )
                    kwargs["releases"] = releases
                    deliver_batches(**kwargs)

                    if not dryrun:
                        for bdr in bdr_list:
                            bdr.redeliver = False
                            bdr.status = BatchDeliveryRelease.STATUS_REDELIVERED
                            bdr.save()

                bdr_ids.extend([bdr.pk for bdr in bdr_list])

        self.stdout.write("Time to process: %s" % (datetime.now() - start_time))

        return "Redeliveries done for bdr_ids %s" % bdr_ids

    def get_bdrs_by_channel_and_type(
        self, bdr_id_start=None, bdr_id_end=None, limit=100
    ):
        """
        {
            "spotify": {
                "insert": [bdr1, bdr2, bdr3],
                "update": [bdr1, bdr2, bdr3],
                "takedown": [bdr1, bdr2, bdr3],
            },
            "soundcloud": {
                "insert": [bdr1, bdr2, bdr3],
                "update": [bdr1, bdr2, bdr3],
                "takedown": [bdr1, bdr2, bdr3],
            }
        }
        """
        bdrs_by_channel_and_type = defaultdict(lambda: defaultdict(set))

        filter_kwargs = {"redeliver": True}

        if bdr_id_start and bdr_id_end:
            filter_kwargs["id__range"] = (bdr_id_start, bdr_id_end)

        bdrs = BatchDeliveryRelease.objects.filter(
            Q(delivery__batch__isnull=False) | Q(delivery__channel=FUGA),
            **filter_kwargs,
        )[:limit]

        for bdr in bdrs:
            # This is a bit unclear as we're only setting an arbitrary attribute
            # on the release-level so we can include the value in the payload to
            # release-delivery. The attribute does not exist on the Release model.
            bdr.release.is_redelivery_for_bdr = bdr.id
            bdrs_by_channel_and_type[bdr.delivery.channel][bdr.get_type_display()].add(
                bdr
            )

        return bdrs_by_channel_and_type
