import json
import math
import sys
from collections import defaultdict
from time import sleep
from uuid import uuid4

from django.conf import settings
from django.core.cache import cache
from django.core.files.base import ContentFile
from django.db.models import Q

from amuse.logging import logger
from amuse.models.bulk_delivery_job_results import BulkDeliveryJobResult
from amuse.models.deliveries import Batch
from amuse.services.delivery.encoder import release_json
from amuse.services.release_delivery_info import ReleaseDeliveryInfo
from amuse.vendor.aws import s3, sqs
from releases.models import Store, ReleaseStoreDeliveryStatus, FugaStores


def trigger_batch_delivery(releases_list, created_by=None):
    batch = Batch.objects.create(status=Batch.STATUS_CREATED, user=created_by)
    batch_id = batch.pk
    logger.info("Delivery batch %s created" % batch_id)

    batch.file.save(
        "%s.json" % str(uuid4()), ContentFile(json.dumps(releases_list).encode('utf-8'))
    )

    logger.info("Delivery file %s stored for batch %s" % (batch.file.url, batch_id))

    message = {
        "id": batch_id,
        "file": s3.create_s3_uri(
            settings.AWS_BATCH_DELIVERY_FILE_BUCKET_NAME, batch.file.name
        ),
    }

    sqs.send_message(settings.RELEASE_DELIVERY_SERVICE_REQUEST_QUEUE, message)
    logger.info("Delivery SQS message %s sent for batch %s" % (message, batch_id))

    batch.status = Batch.STATUS_STARTED
    batch.save()

    mark_delivery_started(releases_list)

    return batch_id


def create_batch_delivery_releases_list(
    delivery_type: str,
    releases: list,
    override_stores: bool = False,
    stores: list = None,
    only_fuga: bool = False,
) -> list:
    if override_stores and stores:
        raise ValueError("Can't specify both override_stores and stores")

    releases_list = []

    for release in releases:
        if override_stores:
            store_list = list(release.included_internal_stores)
        elif stores:
            if "fuga_facebook" in stores and "fuga_instagram" not in stores:
                stores.append("fuga_instagram")
            elif "fuga_instagram" in stores and "fuga_facebook" not in stores:
                stores.append("fuga_facebook")
            store_list = stores
        elif only_fuga:
            # for fuga channels we pass in "full_update" instead of "update" to maintain
            # legacy behaviour (update would return no stores as fuga only supports full updates)
            store_list = list(
                ReleaseDeliveryInfo(release).get_fuga_delivery_channels(
                    "full_update" if delivery_type == "update" else delivery_type
                )
            )
        else:
            release_delivery_info = ReleaseDeliveryInfo(release)
            store_list = release_delivery_info.get_direct_delivery_channels(
                delivery_type
            ) + release_delivery_info.get_fuga_delivery_channels(
                "full_update" if delivery_type == "update" else delivery_type
            )

        releases_list.append(
            {
                "delivery": {
                    "type": delivery_type,
                    "stores": store_list,
                    "countries": list(
                        release.included_countries.values_list("code", flat=True)
                    ),
                    "is_redelivery_for_bdr": getattr(
                        release, "is_redelivery_for_bdr", None
                    ),
                },
                "release": release_json(release),
            }
        )

    return releases_list


def mark_delivery_started(delivery_data):
    for data in delivery_data:
        release_id = data['release']['id']
        previous_stores = cache.get(f'release:{release_id}:started_deliveries', [])
        # Replace all fuga-stores with just 'fuga'
        delivery_stores = set(
            ['fuga' if 'fuga' in s else s for s in data['delivery']['stores']]
        )
        stores = list(delivery_stores | set(previous_stores))
        cache.set(f'release:{release_id}:started_deliveries', stores, timeout=None)


def get_started_deliveries(release_id):
    return cache.get(f'release:{release_id}:started_deliveries', [])


def deliver_batches(
    releases,
    delivery_type,
    override_stores=False,
    stores=None,
    batchsize=None,
    only_fuga=False,
    delay=0,
    dryrun=False,
    job=None,
    user=None,
):
    all_releases_list = list(releases)
    releases_count = len(all_releases_list)

    if releases_count == 0:
        sys.stdout.write("No releases found")
        return

    if batchsize is None:
        batchsize = releases_count

    total_batches = math.ceil(releases_count / batchsize)

    sys.stdout.write(
        "Process %s total releases with stores %s with batchsize %s, total batches %s and delay %s\n"
        % (releases_count, stores, batchsize, total_batches, delay)
    )

    for start in range(0, releases_count, batchsize):
        if start == 0:
            end = batchsize
        elif (start + batchsize) <= releases_count:
            end += batchsize
        else:
            end = releases_count

        releases_in_batch = all_releases_list[start:end]
        current_batch = math.ceil(((start + 1) / batchsize))

        if dryrun:
            sys.stdout.write(
                "Skipping processing of batch %s/%s with slice %s:%s due to dryrun\n"
                % (current_batch, total_batches, start, end)
            )
            continue
        else:
            sys.stdout.write(
                "Start processing batch %s/%s with slice %s:%s \n"
                % (current_batch, total_batches, start, end)
            )

        try:
            releases_list_dict = create_batch_delivery_releases_list(
                delivery_type=delivery_type,
                releases=releases_in_batch,
                override_stores=override_stores,
                only_fuga=only_fuga,
                stores=stores or [],
            )
        except Exception:
            # This is normally reached when there is an issue with a release within
            # the batch and the batch fails. Then we can retry by splitting the
            # batch into single-release batches in order to process the operation
            # for the other releases with no issues and isolate the release
            # that has the issue that will be flagged in the output file as FAILED.
            if not job:
                raise
            sys.stdout.write(
                "Batch %s/%s Failed! Retrying by splitting it into single batches \n"
                % (current_batch, total_batches)
            )
            for release in releases_in_batch:
                result = BulkDeliveryJobResult.objects.filter(
                    job=job,
                    release=release,
                    status=BulkDeliveryJobResult.STATUS_UNPROCESSED,
                )
                try:
                    # Here we retry to perform the operation again for each
                    # individual release that belongs on the failed batch.
                    releases_list_dict = create_batch_delivery_releases_list(
                        delivery_type=delivery_type,
                        releases=[release],
                        override_stores=override_stores,
                        only_fuga=only_fuga,
                        stores=stores or [],
                    )
                except ValueError:
                    # ValueError is thrown for invalid checksum
                    if job:
                        result.update(
                            status=BulkDeliveryJobResult.STATUS_FAILED,
                            description="Operation failed due to invalid coverart checksum",
                        )
                    sys.stdout.write(
                        "Cover art invalid checksum failure for single batch for release_id: %s \n"
                        % release.id
                    )
                except Exception:
                    # Here we isolate any culprit invalid releases and mark them as FAILED
                    if job:
                        result.update(
                            status=BulkDeliveryJobResult.STATUS_FAILED,
                            description="Operation failed due to invalid release",
                        )
                    sys.stdout.write(
                        "Unknown failure for single batch for release_id: %s \n"
                        % release.id
                    )
                else:
                    batch_id = trigger_batch_delivery(releases_list_dict, user)
                    report_batch_results(job, [release], batch_id)
                    sys.stdout.write(
                        "Successful single batch for release_id: %s with batch_id: %s \n"
                        % (release.id, batch_id)
                    )
        else:
            batch_id = trigger_batch_delivery(releases_list_dict, user)
            report_batch_results(job, releases_in_batch, batch_id)
            sys.stdout.write(
                "Successful batch %s/%s that corresponds to batch_id: %s \n"
                % (current_batch, total_batches, batch_id)
            )
        sleep(delay)


def report_batch_results(job, releases_in_batch, batch_id):
    if job:
        BulkDeliveryJobResult.objects.filter(
            job=job,
            release__in=releases_in_batch,
            status=BulkDeliveryJobResult.STATUS_UNPROCESSED,
        ).update(
            status=BulkDeliveryJobResult.STATUS_SUCCESSFUL,
            batch_id=batch_id,
            description="Operation was successfully triggered",
        )


def get_non_delivered_dd_stores(releases, stores=None):
    """
    Returns a dict like this:
        {"deezer": [r_1, r_2], "shazam": [r_2, r_3]}

    Usecase 1:
        Retrieve DD stores approved releases should be sent to
    Usecase 2:
        Retrieve DD stores that haven't been delivered to for a list of releases
    """
    store_releases = defaultdict(list)

    for release in releases:
        delivery_info = ReleaseDeliveryInfo(release)

        # If partially taken-down skip release as we cannot tell if the non-delivered stores should be delivered to
        if ReleaseStoreDeliveryStatus.objects.filter(
            status=ReleaseStoreDeliveryStatus.STATUS_TAKEDOWN, release=release
        ).exists():
            continue

        for store_info in delivery_info.store_delivery_info:
            if stores and store_info['channel_name'] not in stores:
                continue

            # If store should be included in delivery and has no existing delivery data
            if store_info["deliver_to"] and not store_info['delivery_status']:
                store_releases[store_info['channel_name']].append(release)

    assert "fuga_" not in store_releases.keys()

    return dict(store_releases)


def get_taken_down_release_ids(release_ids):
    release_ids = list(map(int, release_ids))
    # Only consider admin active direct feeds and fuga stores with delivery service support
    direct_store_ids = Store.objects.filter(admin_active=True).values_list(
        "id", flat=True
    )
    fuga_store_ids = FugaStores.objects.filter(
        has_delivery_service_support=True
    ).values_list("id", flat=True)

    live_release_ids = (
        ReleaseStoreDeliveryStatus.objects.filter(
            release_id__in=release_ids,
            status=ReleaseStoreDeliveryStatus.STATUS_DELIVERED,
        )
        .filter(Q(store_id__in=direct_store_ids) | Q(fuga_store_id__in=fuga_store_ids))
        .distinct("release_id")
        .values_list("release_id", flat=True)
    )

    return list(set(release_ids) - set(live_release_ids))
