import logging
from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal

from releases.models import Song, Release, ReleaseArtistRole, RoyaltySplit


logger = logging.getLogger(__name__)


VALID_REVISION_STATUS_RULES = [
    {"previous": None, "current": RoyaltySplit.STATUS_PENDING, "next": None},
    {"previous": None, "current": RoyaltySplit.STATUS_ACTIVE, "next": None},
    {
        "previous": None,
        "current": RoyaltySplit.STATUS_ACTIVE,
        "next": RoyaltySplit.STATUS_PENDING,
    },
    {
        "previous": None,
        "current": RoyaltySplit.STATUS_ARCHIVED,
        "next": RoyaltySplit.STATUS_ACTIVE,
    },
    {
        "previous": None,
        "current": RoyaltySplit.STATUS_ARCHIVED,
        "next": RoyaltySplit.STATUS_ARCHIVED,
    },
    {
        "previous": RoyaltySplit.STATUS_ARCHIVED,
        "current": RoyaltySplit.STATUS_ARCHIVED,
        "next": RoyaltySplit.STATUS_ACTIVE,
    },
    {
        "previous": RoyaltySplit.STATUS_ARCHIVED,
        "current": RoyaltySplit.STATUS_ACTIVE,
        "next": RoyaltySplit.STATUS_PENDING,
    },
    {
        "previous": RoyaltySplit.STATUS_ARCHIVED,
        "current": RoyaltySplit.STATUS_ARCHIVED,
        "next": RoyaltySplit.STATUS_ARCHIVED,
    },
    {
        "previous": RoyaltySplit.STATUS_ACTIVE,
        "current": RoyaltySplit.STATUS_PENDING,
        "next": None,
    },
    {
        "previous": RoyaltySplit.STATUS_ARCHIVED,
        "current": RoyaltySplit.STATUS_ACTIVE,
        "next": None,
    },
]


class SplitDataIntegrityError(Exception):
    pass


def validate_splits_for_songs(song_ids, log_error=False, raise_error=False):
    main_primary_artists = get_grouped_main_primary_artists(song_ids)
    splits_grouped_by_song = get_splits_for_songs(song_ids, main_primary_artists)

    results = defaultdict(list)
    results["SETTINGS"] = "%s splits" % len(song_ids)

    validators = {
        "INVALID_RATE": split_revision_rate_is_valid,
        "OWNER_IS_NOT_MAIN_PRIMARY_ARTIST": split_is_owner_is_main_primary_artist,
        "NO_ACTIVE_REVISION": split_has_active_revision_for_released_release,
        "INCORRECT_TIMESERIES": split_has_correct_timeseries,
        "INCORRECT_STATUSES": split_has_correct_statuses,
        "MULTIPLE_IS_OWNER": split_does_not_have_multiple_is_owner,
        "SAME_USER_SPLIT": split_does_not_have_multiple_splits_for_same_user,
    }

    for song_id, data in splits_grouped_by_song.items():
        for error_key, validator_func in validators.items():
            is_valid = validator_func(data)

            if not is_valid:
                error_msg = "song_id: %s, release_id: %s" % (
                    song_id,
                    data[0]["release_id"],
                )
                results[error_key].append(error_msg)

                if log_error:
                    error_msg = "Split validation failure %s: %s" % (
                        error_msg,
                        error_key,
                    )
                    logger.error(error_msg)

                if raise_error:
                    error_msg = "Split validation failure %s: %s" % (
                        error_msg,
                        error_key,
                    )
                    raise SplitDataIntegrityError(error_msg)

    return results


def get_splits_for_songs(song_ids, main_primary_artists):
    kwargs = {"id__in": song_ids}

    splits = list(
        Song.objects.filter(**kwargs)
        .select_related("release", "royalty_splits")
        .order_by("id")
        .values(
            "id",
            "release_id",
            "release__release_date",
            "release__status",
            "royalty_splits__id",
            "royalty_splits__user_id",
            "royalty_splits__start_date",
            "royalty_splits__end_date",
            "royalty_splits__rate",
            "royalty_splits__status",
            "royalty_splits__revision",
            "royalty_splits__is_owner",
        )
    )

    return get_splits_grouped_by_song(splits, main_primary_artists)


def get_splits_grouped_by_song(splits, main_primary_artists):
    grouped_splits = defaultdict(list)

    for split in splits:
        split["release_owner_id"] = main_primary_artists.get(split["release_id"], None)
        grouped_splits[split["id"]].append(split)

    return grouped_splits


def get_grouped_main_primary_artists(song_ids):
    grouped_artists = {}

    main_primary_artists = list(
        ReleaseArtistRole.objects.filter(
            release__songs__id__in=song_ids, main_primary_artist=True
        )
        .select_related("artist")
        .values("release_id", "artist__owner_id")
    )

    for artist in main_primary_artists:
        grouped_artists[artist["release_id"]] = artist["artist__owner_id"]

    return grouped_artists


# TODO should use splits grouped by revision
def split_revision_rate_is_valid(split_data):
    combined_rates = sum([s["royalty_splits__rate"] for s in split_data])
    unique_revisions = len(set([s["royalty_splits__revision"] for s in split_data]))

    if not combined_rates / unique_revisions == Decimal("1.0"):
        return False

    return True


# TODO should use splits grouped by revision
def split_has_active_revision_for_released_release(split_data):
    released_status = [
        Release.STATUS_DELIVERED,
        Release.STATUS_RELEASED,
        Release.STATUS_TAKEDOWN,
    ]
    pending_status = [RoyaltySplit.STATUS_PENDING, RoyaltySplit.STATUS_CONFIRMED]
    status = split_data[0]["release__status"]
    release_date = split_data[0]["release__release_date"]

    if status not in released_status or release_date > date.today():
        return True

    sorted_data = sorted(
        split_data, key=lambda k: k["royalty_splits__revision"], reverse=True
    )

    last_active_revision = sorted_data[0]["royalty_splits__revision"]

    if sorted_data[0]["royalty_splits__status"] in pending_status:
        if last_active_revision == 1:
            return False
        else:
            last_active_revision -= 1

    return all(
        [
            s["royalty_splits__status"] == RoyaltySplit.STATUS_ACTIVE
            for s in sorted_data
            if s["royalty_splits__revision"] == last_active_revision
        ]
    )


# TODO should use splits grouped by revision
def split_is_owner_is_main_primary_artist(split_data):
    for split in split_data:
        is_owner = split["royalty_splits__is_owner"]
        split_owner_id = split["royalty_splits__user_id"]
        main_primary_artist_owner_id = split["release_owner_id"]

        if is_owner is True and split_owner_id != main_primary_artist_owner_id:
            return False

        if is_owner is False and split_owner_id == main_primary_artist_owner_id:
            return False

    return True


# TODO should use splits grouped by revision
def split_has_correct_timeseries(split_data):
    revisions = {s["royalty_splits__revision"] for s in split_data}
    sorted_data = sorted(split_data, key=lambda k: k["royalty_splits__revision"])
    unique_revision_dates = {
        (
            s["royalty_splits__revision"],
            s["royalty_splits__start_date"],
            s["royalty_splits__end_date"],
        )
        for s in sorted_data
    }

    # All splits in a revision should have the same dates
    if len(unique_revision_dates) != len(revisions):
        return False

    time_series = []
    for revision, start_date, end_date in list(unique_revision_dates):
        time_series.append(
            {"revision": revision, "start_date": start_date, "end_date": end_date}
        )

    sorted_time_series = sorted(time_series, key=lambda k: k["revision"])
    first_start_date = sorted_time_series[0]["start_date"]
    last_end_date = sorted_time_series[-1]["end_date"]

    # First and last dates should always be None
    if first_start_date is not None or last_end_date is not None:
        return False

    # Only one revision so nothing else to validate
    if len(sorted_time_series) == 1:
        return True

    # Current revision start_date - 1 day should equal previous revision end_date
    for idx, item in enumerate(sorted_time_series):
        if idx != 0:
            end_date = sorted_time_series[idx - 1]["end_date"]
            if item["start_date"] - timedelta(days=1) != end_date:
                # Revision 1 active and revision 1 pending will have end_date=None
                # until revision 2 splits have been activated.
                if end_date is not None:
                    return False

    return True


def split_has_correct_statuses(split_data):
    """
    all splits in a revision must either be
    - active
    - archived
    - pending/confirmed

    pending/confirmed must always be last revision
    cannot only have confirmed. must be in combination with pending
    archived must be before active
    archived must be first revision or come after another archived revision
    """
    grouped_splits = _group_splits_by_revision(split_data)
    allowed_multi_status = [RoyaltySplit.STATUS_PENDING, RoyaltySplit.STATUS_CONFIRMED]
    active_status = [RoyaltySplit.STATUS_ACTIVE, RoyaltySplit.STATUS_ARCHIVED]
    status_dict = {}

    for revision, splits in grouped_splits.items():
        status_dict[revision] = sorted(
            list({s["royalty_splits__status"] for s in splits})
        )

        # Check if multi status are allowed types
        # Set revision-level status to pending for easier handling
        if len(status_dict[revision]) > 1:
            if status_dict[revision] == allowed_multi_status:
                status_dict[revision] = [RoyaltySplit.STATUS_PENDING]
            else:
                return False

    # Split revisions for this song doesn't start with 1
    if status_dict.get(1, False) is False:
        return False

    return _validate_status_by_revision(status_dict)


def split_does_not_have_multiple_is_owner(split_data):
    grouped_splits = _group_splits_by_revision(split_data)

    for _, splits in grouped_splits.items():
        owners_per_revision = sum([s["royalty_splits__is_owner"] for s in splits])
        if owners_per_revision > 1:
            return False

    return True


def split_does_not_have_multiple_splits_for_same_user(split_data):
    grouped_splits = _group_splits_by_revision(split_data)

    for _, splits in grouped_splits.items():
        users_per_revision = [
            s["royalty_splits__user_id"]
            for s in splits
            if s["royalty_splits__user_id"] is not None
        ]

        if len(users_per_revision) != len(set(users_per_revision)):
            return False

    return True


def split_revision_order_is_correct(split_data):
    grouped_splits = _group_splits_by_revision(split_data)
    revisions = sorted(grouped_splits.keys())
    first_revision = min(revisions)
    last_revision = max(revisions)
    consecutive_revisions = list(range(first_revision, last_revision + 1))

    if first_revision != 1 or revisions != consecutive_revisions:
        return False

    return True


def _group_splits_by_revision(split_data):
    grouped_splits = defaultdict(list)

    for split in split_data:
        grouped_splits[split["royalty_splits__revision"]].append(split)

    return grouped_splits


def _validate_status_by_revision(status_dict):
    """
    Check if status is valid revision by revision. Accepts a sorted dict starting from
    revision 1.

    dict lookup example given `revision1: Archived` and `revision2: Active` splits:
        Revision 1. prev: None, current: Archived, next: Active
        Revision 2. prev: Archived, current: Active, next: None
    """
    last_revision = len(status_dict)

    for revision, status_list in status_dict.items():
        status = status_list[0]
        prev_status = status_dict[revision - 1][0] if revision > 1 else None
        next_status = status_dict[revision + 1][0] if revision < last_revision else None

        status_state = {"previous": prev_status, "current": status, "next": next_status}

        if status_state not in VALID_REVISION_STATUS_RULES:
            return False

    return True
