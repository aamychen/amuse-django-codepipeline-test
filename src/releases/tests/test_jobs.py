import json
from datetime import date, timedelta, datetime

import pytest
from unittest import mock, TestCase

from django.test import override_settings

from releases.models import Release, ReleaseArtistRole
from releases.tests.factories import (
    RoyaltySplitFactory,
    ReleaseFactory,
    ReleaseArtistRoleFactory,
    CoverArtFactory,
)
from releases.jobs import (
    splits_integrity_check,
    create_smart_links_for_pre_releases,
    create_or_update_smart_links_for_releases,
    email_smart_links_on_release_day,
    update_delivered,
)

from users.tests.factories import Artistv2Factory, UserFactory


@pytest.mark.django_db
class RoyaltySplitIntegrityCheckTestCase(TestCase):
    @mock.patch("amuse.tasks.zendesk_create_or_update_user")
    def setUp(self, mock_zendesk):
        super().setUp()

        RoyaltySplitFactory()

    @mock.patch(
        "releases.validators.split_is_owner_is_main_primary_artist", return_value=True
    )
    @mock.patch("releases.validators.split_revision_rate_is_valid", return_value=True)
    def test_split_revision_rate_is_valid(
        self, mock_rate_is_valid, mock_owner_is_valid
    ):
        results = json.loads(splits_integrity_check())

        assert len(results) == 1
        assert "splits" in results["SETTINGS"]

    @mock.patch(
        "releases.validators.split_is_owner_is_main_primary_artist", return_value=True
    )
    @mock.patch("releases.validators.split_revision_rate_is_valid", return_value=False)
    def test_split_revision_rate_is_not_valid(
        self, mock_rate_is_valid, mock_owner_is_valid
    ):
        results = json.loads(splits_integrity_check())

        assert len(results) == 2
        assert "splits" in results["SETTINGS"]
        assert "song_id:" in results["INVALID_RATE"][0]

    @mock.patch(
        "releases.validators.split_has_active_revision_for_released_release",
        return_value=False,
    )
    @mock.patch(
        "releases.validators.split_is_owner_is_main_primary_artist", return_value=False
    )
    @mock.patch("releases.validators.split_revision_rate_is_valid", return_value=False)
    def test_split_multiple_errors(
        self, mock_rate_is_valid, mock_owner_is_valid, mock_active_revision
    ):
        results = json.loads(splits_integrity_check())

        assert len(results) == 4
        assert "splits" in results["SETTINGS"]
        assert "song_id:" in results["INVALID_RATE"][0]
        assert "song_id:" in results["OWNER_IS_NOT_MAIN_PRIMARY_ARTIST"][0]
        assert "song_id:" in results["NO_ACTIVE_REVISION"][0]


@mock.patch('amuse.vendor.spotify.spotify_api.SpotifyAPI.fetch_spotify_album_by_upc')
@mock.patch("amuse.services.smart_link.send_smart_link_creation_data_to_link_service")
@mock.patch("amuse.tasks.save_cover_art_checksum")
@mock.patch("django.db.models.signals.ModelSignal.send")
@pytest.mark.django_db
def test_create_smart_links_for_releases(
    _,
    __,
    send_smart_link_creation_data_to_link_service_mock,
    fetch_spotify_album_by_upc_mock,
):
    fetch_spotify_album_by_upc_mock.return_value = {'id': 'mock-id'}
    mock_releases = ReleaseFactory.create_batch(
        type=1,
        link=None,
        status=Release.STATUS_RELEASED,
        size=20,
        release_date=date.today(),
        countries=[],
        stores=0,
        schedule_type=Release.SCHEDULE_TYPE_STATIC,
    )

    mock_releases.append(
        ReleaseFactory(
            type=1,
            link=None,
            status=Release.STATUS_RELEASED,
            release_date=date.today(),
            stores=0,
            schedule_type=Release.SCHEDULE_TYPE_ASAP,
        )
    )
    mock_releases.append(
        ReleaseFactory(
            type=1,
            link=None,
            status=Release.STATUS_RELEASED,
            release_date=date.today() - timedelta(days=1),
            stores=0,
            schedule_type=Release.SCHEDULE_TYPE_ASAP,
        )
    )
    mock_releases.append(
        ReleaseFactory(
            type=1,
            link=None,
            status=Release.STATUS_RELEASED,
            release_date=date.today() - timedelta(days=5),
            stores=0,
            schedule_type=Release.SCHEDULE_TYPE_ASAP,
        )
    )

    # old mock releases
    ReleaseFactory.create_batch(
        type=1,
        link=None,
        status=Release.STATUS_RELEASED,
        size=5,
        release_date=date.today() - timedelta(days=1),
        countries=[],
        stores=0,
    )
    # future mock releases
    ReleaseFactory.create_batch(
        type=1,
        link=None,
        status=Release.STATUS_RELEASED,
        size=5,
        release_date=date.today() + timedelta(days=1),
        countries=[],
        stores=0,
    )
    ReleaseFactory(
        type=1,
        link=None,
        status=Release.STATUS_RELEASED,
        release_date=date.today() - timedelta(days=6),
        stores=0,
        schedule_type=Release.SCHEDULE_TYPE_ASAP,
    )

    mock_artist = Artistv2Factory.create(name='Test')

    for mock_release in mock_releases:
        ReleaseArtistRoleFactory.create(release=mock_release, artist=mock_artist)
        CoverArtFactory.create(release=mock_release)

    messages = [
        dict(
            type='album',
            amuse_release_id=mock_release.id,
            song_id=None,
            name=mock_release.name,
            image=mock_release.cover_art.thumbnail_url_400,
            artist_name=mock_artist.name,
            upc=str(mock_release.upc),
            isrc=None,
            countries_encoded=0,
            stores=0,
            status=mock_release.status,
        )
        for mock_release in mock_releases
    ]

    # set batch size to 1 so function for creating
    # or updating smart links is called 20 times
    # (once per eligible every release)
    with override_settings(SMART_LINK_MESSAGE_BATCH_SIZE=1):
        mock_calls = [mock.call([msg]) for msg in messages]
        create_or_update_smart_links_for_releases()
        send_smart_link_creation_data_to_link_service_mock.assert_has_calls(
            mock_calls, any_order=True
        )


@mock.patch("amuse.services.smart_link.send_smart_link_creation_data_to_link_service")
@mock.patch("amuse.tasks.save_cover_art_checksum")
@mock.patch("django.db.models.signals.ModelSignal.send")
@pytest.mark.django_db
def test_create_smart_links_for_pre_releases(
    _, __, send_smart_link_creation_data_to_link_service_mock
):
    mock_releases = ReleaseFactory.create_batch(
        type=1, link=None, status=Release.STATUS_DELIVERED, size=20
    )
    mock_artist = Artistv2Factory.create(name='Test')

    # released mock releases (these should not be sent)
    ReleaseFactory.create_batch(
        type=1, link=None, status=Release.STATUS_RELEASED, size=5
    )

    for mock_release in mock_releases:
        ReleaseArtistRoleFactory.create(release=mock_release, artist=mock_artist)
        CoverArtFactory.create(release=mock_release)

    messages = [
        dict(
            type='album',
            amuse_release_id=mock_release.id,
            song_id=None,
            name=mock_release.name,
            image=mock_release.cover_art.thumbnail_url_400,
            artist_name=mock_artist.name,
            include_pre_save_link=mock_release.include_pre_save_link,
            stores=0,
            status=mock_release.status,
        )
        for mock_release in mock_releases
    ]

    # set batch size to 1 so function for creating
    # smart links is called 20 times
    # (once per eligible every release)
    with override_settings(SMART_LINK_MESSAGE_BATCH_SIZE=1):
        mock_calls = [mock.call([msg]) for msg in messages]
        create_smart_links_for_pre_releases()
        send_smart_link_creation_data_to_link_service_mock.assert_has_calls(
            mock_calls, any_order=True
        )


@mock.patch("django.db.models.signals.ModelSignal.send")
@mock.patch('amuse.vendor.segment.events.send_smart_link_release_email')
@pytest.mark.django_db
def test_email_smart_links_on_release_day_owner_is_creator(
    smart_link_release_email_mock, _
):
    mock_owner = mock_creator = UserFactory.create()
    mock_link = 'https://share.amuse.io'
    ReleaseFactory.create(
        user=mock_owner,
        created_by=mock_creator,
        release_date=date.today(),
        status=Release.STATUS_RELEASED,
        link=mock_link,
    )
    email_smart_links_on_release_day()
    smart_link_release_email_mock.assert_called_once_with(mock_owner.id, mock_link)


@mock.patch("django.db.models.signals.ModelSignal.send")
@mock.patch('amuse.vendor.segment.events.send_smart_link_release_email')
@pytest.mark.django_db
def test_email_smart_links_on_release_day_owner_is_not_creator(
    smart_link_release_email_mock, _
):
    mock_owner, mock_creator = UserFactory.create_batch(size=2)
    mock_link = 'https://share.amuse.io'
    ReleaseFactory.create(
        user=mock_owner,
        created_by=mock_creator,
        release_date=date.today(),
        status=Release.STATUS_RELEASED,
        link=mock_link,
    )
    email_smart_links_on_release_day()

    mock_calls = [
        mock.call(mock_creator.id, mock_link),
        mock.call(mock_owner.id, mock_link),
    ]
    smart_link_release_email_mock.assert_has_calls(calls=mock_calls)


@mock.patch("django.db.models.signals.ModelSignal.send")
@mock.patch('time.sleep')
@mock.patch('amuse.vendor.segment.events.send_smart_link_release_email')
@pytest.mark.django_db
def test_email_smart_links_on_release_day_throttle_every_100_releases(
    smart_link_release_email_mock, time_sleep_mock, _
):
    ReleaseFactory.create_batch(
        release_date=date.today(), status=Release.STATUS_RELEASED, size=200
    )
    email_smart_links_on_release_day()
    mock_calls = [mock.call(1.5), mock.call(1.5)]
    time_sleep_mock.assert_has_calls(calls=mock_calls)


@mock.patch('amuse.vendor.segment.events.send_release_released')
@mock.patch("django.db.models.signals.ModelSignal.send")
@pytest.mark.django_db
def test_update_delivered_event_triggered(_, mock_event_released):
    delivered_releases = ReleaseFactory.create_batch(
        status=Release.STATUS_DELIVERED, release_date=date.today(), size=2
    )
    ReleaseArtistRoleFactory(
        artist=Artistv2Factory(),
        release=delivered_releases[0],
        role=ReleaseArtistRole.ROLE_PRIMARY_ARTIST,
        main_primary_artist=True,
    )
    ReleaseArtistRoleFactory(
        artist=Artistv2Factory(),
        release=delivered_releases[1],
        role=ReleaseArtistRole.ROLE_PRIMARY_ARTIST,
        main_primary_artist=True,
    )

    update_delivered()

    mock_event_data_1 = {
        "owner_id": delivered_releases[0].user.id,
        "release_id": delivered_releases[0].id,
        "release_name": delivered_releases[0].name,
        "release_status": delivered_releases[0].STATUS_RELEASED,
        "main_primary_artist": delivered_releases[0].main_primary_artist.name,
        "release_date": delivered_releases[0].release_date,
        "release_flags": [],
        "songs_with_flags": [],
        "schedule_type": "static",
    }
    mock_event_data_2 = {
        "owner_id": delivered_releases[1].user.id,
        "release_id": delivered_releases[1].id,
        "release_name": delivered_releases[1].name,
        "release_status": delivered_releases[1].STATUS_RELEASED,
        "main_primary_artist": delivered_releases[1].main_primary_artist.name,
        "release_date": delivered_releases[1].release_date,
        "release_flags": [],
        "songs_with_flags": [],
        "schedule_type": "static",
    }

    mock_calls = [mock.call(mock_event_data_1), mock.call(mock_event_data_2)]
    mock_event_released.assert_has_calls(calls=mock_calls, any_order=True)
