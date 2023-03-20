import json
from unittest import mock
import pytest

from django.core.management import call_command


RESULT_DICT = {"key": "works!"}
OUTPUT_MSG = "Validate splits for 0 songs\n%s\n" % json.dumps(RESULT_DICT)


@mock.patch(
    "releases.management.commands.validate_splits.validate_splits_for_songs",
    return_value=RESULT_DICT,
)
@mock.patch("releases.models.Song.objects")
def test_validate_splits_with_no_args(mock_songs, mock_validate, capsys):
    call_command("validate_splits")
    captured = capsys.readouterr()
    assert captured.out == OUTPUT_MSG


@mock.patch(
    "releases.management.commands.validate_splits.validate_splits_for_songs",
    return_value=RESULT_DICT,
)
@mock.patch("releases.models.Song.objects")
def test_validate_splits_with_args(mock_songs, mock_validate, capsys):
    call_command("validate_splits", "--start-date=2020-01-01", "--end-date=2020-01-15")
    captured = capsys.readouterr()
    assert captured.out == OUTPUT_MSG
