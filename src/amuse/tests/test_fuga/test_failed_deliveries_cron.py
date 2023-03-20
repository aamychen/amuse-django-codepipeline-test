from ftplib import FTP
from ftplib import error_perm
from unittest import mock
from unittest.mock import call

import pytest
import responses

from django.test import override_settings

from amuse.vendor.fuga.cronjob import (
    failed_release_upc_codes,
    mark_releases_as_undeliverable,
    remove_ingestion_failed_releases,
    update_ingestion_failed_releases,
)
from amuse.tests.helpers import (
    add_zendesk_mock_post_response,
    ZENDESK_MOCK_API_URL_TOKEN,
)
from releases.models import Release, Comments
from releases.tests.factories import ReleaseFactory
from amuse.vendor.fuga.delivery import FugaFTPConnection


def test_upc_codes_fetched_from_ingestion_failed_directory():
    ftp_mock = mock.create_autospec(FTP)

    failed_release_upc_codes(ftp_mock)

    assert ftp_mock.method_calls[0] == call.cwd('/ingestion_failed')


def test_get_failed_upc_codes():
    ftp_mock = mock.create_autospec(FTP)

    expected_upc_codes = ['upc1', 'upc2', 'upc3']
    ftp_mock.nlst.return_value = expected_upc_codes

    upc_codes = failed_release_upc_codes(ftp_mock)

    assert upc_codes == expected_upc_codes


@pytest.mark.django_db
@responses.activate
@override_settings(**ZENDESK_MOCK_API_URL_TOKEN)
def test_delivered_release_is_marked_as_undeliverable():
    add_zendesk_mock_post_response()
    release = ReleaseFactory(status=Release.STATUS_DELIVERED)

    successful_upc_codes = mark_releases_as_undeliverable([release.upc_code])

    release.refresh_from_db()

    assert successful_upc_codes == [release.upc_code]
    assert release.status == Release.STATUS_UNDELIVERABLE


@pytest.mark.django_db
@responses.activate
@override_settings(**ZENDESK_MOCK_API_URL_TOKEN)
def test_undeliverable_release_gets_comment():
    add_zendesk_mock_post_response()
    release = ReleaseFactory(status=Release.STATUS_DELIVERED)

    mark_releases_as_undeliverable([release.upc_code])

    release.refresh_from_db()

    assert 'FUGA ingestion failed' in release.comments.text


@pytest.mark.django_db
@responses.activate
@override_settings(**ZENDESK_MOCK_API_URL_TOKEN)
def test_existing_release_comment_not_removed_by_ingestion_failed_text():
    add_zendesk_mock_post_response()
    release = ReleaseFactory(status=Release.STATUS_DELIVERED)

    Comments.objects.create(release=release, text='Previous text')

    mark_releases_as_undeliverable([release.upc_code])

    release.refresh_from_db()

    assert release.comments.text.endswith('Previous text')


@pytest.mark.django_db
@responses.activate
@override_settings(**ZENDESK_MOCK_API_URL_TOKEN)
def test_release_not_delivered_will_succeed_so_ftp_directory_can_be_deleted_later():
    add_zendesk_mock_post_response()
    release = ReleaseFactory(status=Release.STATUS_APPROVED)

    successful_upc_codes = mark_releases_as_undeliverable([release.upc_code])

    assert successful_upc_codes == [release.upc_code]


@pytest.mark.django_db
@responses.activate
@override_settings(**ZENDESK_MOCK_API_URL_TOKEN)
def test_release_not_in_delivered_state_will_not_be_marked_undeliverable():
    add_zendesk_mock_post_response()
    release = ReleaseFactory(status=Release.STATUS_APPROVED)

    mark_releases_as_undeliverable([release.upc_code])

    release.refresh_from_db()

    assert release.status == Release.STATUS_APPROVED


def test_failed_upc_directory_will_be_emptied_of_files():
    def upc_directory_nlst(directory):
        if directory == f'/ingestion_failed/{upc_code}':
            return directory_files

    ftp_mock = mock.create_autospec(FTP)
    ftp_mock.nlst.side_effect = upc_directory_nlst

    upc_code = 'upc1'
    directory_files = ['file1', 'file2', 'file3']

    remove_ingestion_failed_releases(ftp_mock, ['upc1'])
    for filename in directory_files:
        assert next(
            filter(
                lambda c: c == call.delete(f'/ingestion_failed/{upc_code}/{filename}'),
                ftp_mock.method_calls,
            )
        )


def test_failed_upc_directory_will_be_deleted():
    ftp_mock = mock.create_autospec(FTP)
    ftp_mock.nlst.return_value = []

    remove_ingestion_failed_releases(ftp_mock, ['upc1'])

    assert ftp_mock.method_calls[-1] == call.rmd('/ingestion_failed/upc1')


@mock.patch('amuse.vendor.fuga.cronjob.logger.warning')
@mock.patch('ftplib.FTP.cwd', autospec=True)
@mock.patch('ftplib.FTP.quit', autospec=True)
def test_update_ingestion_failed_releases_error_handling(
    mock_ftp_conn_quit, mock_ftp_conn_cwd, mock_logger
):
    mock_ftp_conn_cwd.side_effect = error_perm("CWD error")
    mock_ftp_conn_quit.return_value = None
    update_ingestion_failed_releases()
    mock_ftp_conn_cwd.assert_called_once()
    mock_logger.assert_called_once_with(
        "FUGA update ingestion failed releases FAILED with error CWD error"
    )
