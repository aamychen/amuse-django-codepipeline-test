import pytest

from releases.validators import (
    split_has_correct_timeseries,
    split_does_not_have_multiple_is_owner,
    split_does_not_have_multiple_splits_for_same_user,
    split_has_correct_statuses,
    split_revision_order_is_correct,
    split_revision_rate_is_valid,
    split_has_active_revision_for_released_release,
    split_is_owner_is_main_primary_artist,
)
from releases.tests.helpers import (
    splits_with_incorrect_rates,
    splits_with_incorrect_dates_1,
    splits_with_incorrect_dates_2,
    splits_with_incorrect_dates_3,
    splits_with_incorrect_dates_4,
    splits_with_incorrect_dates_5,
    splits_with_correct_dates_1,
    splits_with_correct_dates_2,
    splits_with_correct_dates_3,
    splits_with_correct_single_is_owner,
    splits_with_incorrect_multiple_is_owner,
    splits_with_correct_single_user_1,
    splits_with_correct_single_user_2,
    splits_with_correct_no_user,
    splits_with_incorrect_multiple_user_1,
    splits_with_incorrect_multiple_user_2,
    splits_with_correct_status_1,
    splits_with_correct_status_2,
    splits_with_correct_status_3,
    splits_with_correct_status_4,
    splits_with_correct_status_5,
    splits_with_correct_status_6,
    splits_with_correct_status_7,
    splits_with_correct_status_8,
    splits_with_incorrect_status_1,
    splits_with_incorrect_status_2,
    splits_with_incorrect_status_3,
    splits_with_incorrect_status_4,
    splits_with_incorrect_status_5,
    splits_with_incorrect_status_6,
    splits_with_incorrect_status_7,
    splits_with_correct_revisions_1,
    splits_with_correct_revisions_2,
    splits_with_incorrect_revisions_1,
    splits_with_incorrect_revisions_2,
    splits_with_correct_rates,
    splits_with_incorrect_rates,
    splits_with_correct_is_owner_true,
    splits_with_correct_is_owner_false,
    splits_with_incorrect_is_owner_true,
    splits_with_incorrect_is_owner_false,
    splits_with_active_revision,
    splits_with_active_revision_2,
    splits_with_active_revision_3,
    splits_with_active_revision_4,
    splits_with_no_active_revision,
    splits_with_no_active_revision_2,
)


@pytest.mark.parametrize(
    "splits,result",
    [
        (splits_with_correct_dates_1, True),
        (splits_with_correct_dates_2, True),
        (splits_with_correct_dates_3, True),
        (splits_with_incorrect_dates_1, False),
        (splits_with_incorrect_dates_2, False),
        (splits_with_incorrect_dates_3, False),
        (splits_with_incorrect_dates_4, False),
        (splits_with_incorrect_dates_5, False),
    ],
)
def test_split_has_correct_timeseries(splits, result):
    assert split_has_correct_timeseries(splits) is result


@pytest.mark.parametrize(
    "splits,result",
    [
        (splits_with_correct_single_is_owner, True),
        (splits_with_incorrect_multiple_is_owner, False),
    ],
)
def test_split_does_not_have_multiple_is_owner(splits, result):
    assert split_does_not_have_multiple_is_owner(splits) is result


@pytest.mark.parametrize(
    "splits,result",
    [
        (splits_with_correct_no_user, True),
        (splits_with_correct_single_user_1, True),
        (splits_with_correct_single_user_2, True),
        (splits_with_incorrect_multiple_user_1, False),
        (splits_with_incorrect_multiple_user_2, False),
    ],
)
def test_split_does_not_have_multiple_splits_for_same_user(splits, result):
    assert split_does_not_have_multiple_splits_for_same_user(splits) is result


@pytest.mark.parametrize(
    "splits,result",
    [
        (splits_with_correct_status_1, True),
        (splits_with_correct_status_2, True),
        (splits_with_correct_status_3, True),
        (splits_with_correct_status_4, True),
        (splits_with_correct_status_5, True),
        (splits_with_correct_status_6, True),
        (splits_with_correct_status_7, True),
        (splits_with_correct_status_8, True),
        (splits_with_incorrect_status_1, False),
        (splits_with_incorrect_status_2, False),
        (splits_with_incorrect_status_3, False),
        (splits_with_incorrect_status_4, False),
        (splits_with_incorrect_status_5, False),
        (splits_with_incorrect_status_6, False),
        (splits_with_incorrect_status_7, False),
    ],
)
def test_split_has_correct_statuses(splits, result):
    assert split_has_correct_statuses(splits) is result


@pytest.mark.parametrize(
    "splits,result",
    [
        (splits_with_correct_revisions_1, True),
        (splits_with_correct_revisions_2, True),
        (splits_with_incorrect_revisions_1, False),
        (splits_with_incorrect_revisions_2, False),
    ],
)
def test_split_revision_order_is_correct(splits, result):
    assert split_revision_order_is_correct(splits) is result


def test_split_revision_rate_is_valid_detects_correct_rate():
    assert split_revision_rate_is_valid(splits_with_correct_rates)


def test_split_revision_rate_is_valid_detects_incorrect_rate():
    assert split_revision_rate_is_valid(splits_with_incorrect_rates) is False


@pytest.mark.parametrize(
    "splits,result",
    [
        (splits_with_correct_is_owner_true, True),
        (splits_with_correct_is_owner_false, True),
        (splits_with_incorrect_is_owner_true, False),
        (splits_with_incorrect_is_owner_false, False),
    ],
)
def test_split_is_owner_is_main_primary_artist(splits, result):
    assert split_is_owner_is_main_primary_artist(splits) is result


@pytest.mark.parametrize(
    "splits,result",
    [
        (splits_with_active_revision, True),
        (splits_with_active_revision_2, True),
        (splits_with_active_revision_3, True),
        (splits_with_active_revision_4, True),
        (splits_with_no_active_revision, False),
        (splits_with_no_active_revision_2, False),
    ],
)
def test_split_has_active_revision(splits, result):
    assert split_has_active_revision_for_released_release(splits) is result
