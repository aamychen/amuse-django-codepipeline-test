import json
import logging
import sys
from collections import defaultdict

from dateutil.parser import isoparse
from django.core.management.base import BaseCommand
from django.core.serializers.json import DjangoJSONEncoder
from django.db.models import Subquery
from django.forms.models import model_to_dict

from releases.models import RoyaltySplit, Song


logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Repair broken splits. Check source for available fixes."

    def add_arguments(self, parser):
        parser.add_argument('--fix-type', type=str)
        parser.add_argument(
            "--start-date",
            type=isoparse,
            help="Release dates starting from this date. Example: 2019-01-01",
        )
        parser.add_argument(
            "--end-date",
            type=isoparse,
            help="Release dates up until this date. Example: 2019-12-31",
        )
        parser.add_argument(
            '--release-ids',
            nargs='+',
            type=int,
            help='Single/multiple release_ids separated by space. Example: 1 2 3 4',
        )
        parser.add_argument(
            '--dry-run',
            dest='is_dry_run',
            action='store_true',
            help='Just print, do not update',
            default=False,
        )

    def handle(self, *args, **kwargs):
        fix_type = kwargs.get('fix_type')
        release_ids = kwargs.get('release_ids')
        is_dry_run = kwargs.get("is_dry_run", False)
        results = {"FIX_TYPE": fix_type, "IS_DRY_RUN": is_dry_run}
        start_date = kwargs.get("start_date", None)
        end_date = kwargs.get("end_date", None)

        if bool(start_date) is not bool(end_date):
            self.stdout.write(
                "Both start and end date must be specified or none of them"
            )
            return

        if not fix_type:
            self.stderr.write("Specify what type of fix to run with --fix-type")
            return

        self.stdout.write("Run fix for %s" % fix_type)

        kwargs = {}
        song_kwargs = {}

        if release_ids:
            kwargs["song__release_id__in"] = release_ids
            song_kwargs["release_id__in"] = release_ids
            self.stdout.write("Processing release_ids %s" % release_ids)

        if start_date and end_date:
            kwargs["song__release__release_date__range"] = (start_date, end_date)
            song_kwargs["release__release_date__range"] = (start_date, end_date)

        locked_splits = RoyaltySplit.objects.filter(is_locked=True)
        song_ids_with_locked_splits = list(
            Song.objects.filter(
                id__in=Subquery(locked_splits.values("song_id")), **song_kwargs
            ).values_list("id", flat=True)
        )

        if fix_type == "invalid_owner":
            fix_invalid_owner(is_dry_run, kwargs, song_ids_with_locked_splits)
        elif fix_type == "same_user":
            results["SAME_USER"] = fix_same_user(
                is_dry_run, kwargs, song_ids_with_locked_splits
            )
        else:
            self.stderr.write("%s is not a valid option for --fix-type" % fix_type)
            return

        json_results = json.dumps(results, cls=DjangoJSONEncoder)
        logger.info("Repair splits %s" % json_results)

        return json_results


def fix_same_user(is_dry_run=False, kwargs={}, song_ids_with_locked_splits=None):
    splits = RoyaltySplit.objects.filter(**kwargs).exclude(
        song_id__in=song_ids_with_locked_splits
    )

    if not splits:
        sys.stdout.write("No splits found")
        return

    updates = get_same_user_updates(splits)
    splits_to_update = updates["to_update"]
    splits_to_delete = updates["to_delete"]

    if is_dry_run is False:
        # bulk_update() only available in django>=2.2.x
        for split in splits_to_update:
            split.save()

        RoyaltySplit.objects.filter(id__in=[s.id for s in splits_to_delete]).delete()

    return {
        "UPDATE_SPLITS": [model_to_dict(s) for s in splits_to_update],
        "DELETE_SPLITS": [model_to_dict(s) for s in splits_to_delete],
    }


def fix_invalid_owner(is_dry_run=False, kwargs={}, song_ids_with_locked_splits=None):
    invalid_true_owner_splits = (
        RoyaltySplit.objects.invalid_true_owner()
        .filter(**kwargs)
        .exclude(song_id__in=song_ids_with_locked_splits)
    )
    invalid_false_owner_splits = (
        RoyaltySplit.objects.invalid_false_owner()
        .filter(**kwargs)
        .exclude(song_id__in=song_ids_with_locked_splits)
    )

    sys.stdout.write(
        "Found splits with is_owner=True and user != owner\n%s"
        % log_splits(invalid_true_owner_splits)
    )
    sys.stdout.write(
        "Found splits with is_owner=False and user == owner\n%s"
        % log_splits(invalid_false_owner_splits)
    )

    splits_count = len(invalid_true_owner_splits) + len(invalid_false_owner_splits)

    if is_dry_run is False:
        invalid_true_owner_splits.update(is_owner=False)
        invalid_false_owner_splits.update(is_owner=True)

    sys.stdout.write("Updated %s splits" % splits_count)


def get_same_user_updates(splits):
    """
    Returns a dict to avoid mixing up return values and appropriate actions.
    """
    splits_ordered_by_song_revision = splits.filter(user_id__isnull=False).order_by(
        "song_id", "revision", "user_id"
    )
    splits_dict = defaultdict(list)
    splits_to_update = []
    splits_to_delete = []
    unique_key = None
    previous_key = None

    for split in splits_ordered_by_song_revision.iterator():
        unique_key = "%s_%s_%s" % (split.song_id, split.revision, split.user_id)
        splits_dict[unique_key].append(split)

        if previous_key and previous_key != unique_key:
            if len(splits_dict[previous_key]) == 1:
                del splits_dict[previous_key]

        previous_key = unique_key

    # Check last item as well as it's not processed in for loop
    if unique_key and len(splits_dict[unique_key]) == 1:
        del splits_dict[unique_key]

    for unique_key, splits in splits_dict.items():
        split_to_keep = splits[-1]  # Keep oldest split
        duplicated_splits = splits[:-1]

        split_to_keep.rate += sum(s.rate for s in duplicated_splits)
        split_to_keep.is_owner = split_to_keep._get_is_owner()
        splits_to_update.append(split_to_keep)
        splits_to_delete += duplicated_splits

    return {"to_update": splits_to_update, "to_delete": splits_to_delete}


def log_splits(splits):
    return [
        {"id": s.id, "song_id": s.song_id, "release_id": s.song.release_id}
        for s in splits
    ]
