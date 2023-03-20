from unittest import mock

from django.core.management import call_command


@mock.patch("amuse.management.commands.create_hyperwallet_report.get_payments")
@mock.patch("amuse.management.commands.create_hyperwallet_report.time")
@mock.patch("builtins.open")
def test_throttle_and_incremental_write_works(mock_open, mock_time, mock_get_payments):
    mock_get_payments.side_effect = [
        {"count": 1, "data": []},
        {"count": 1, "data": []},
        None,
    ]

    call_command(
        "create_hyperwallet_report",
        start_date="2020-01-01",
        end_date="2020-01-31",
        limit=100,
    )

    file_name = '/tmp/hyperwallet_report_2020-01-01_2020-01-31.csv'

    assert mock_open.call_args_list[0] == mock.call(file_name, 'w+')
    assert mock_open.call_args_list[1] == mock.call(file_name, 'a+')
    assert mock_open.call_args_list[2] == mock.call(file_name, 'a+')

    assert mock_time.sleep.call_args_list[0] == mock.call(0.6)
    assert mock_time.sleep.call_args_list[1] == mock.call(0.6)
