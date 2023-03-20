from unittest import mock

import pytest
from django.test import override_settings

from amuse.services.smart_link import amuse_smart_link_callback, SmartLinkStoreFlags
from amuse.services.smart_link import (
    send_smart_link_creation_data_to_link_service,
    create_pre_release_smart_link_message_payload,
    create_release_smart_link_message_payload,
    translate_release_type_to_smart_link_service_type,
    email_smart_link_delivered_releases,
)
from countries.tests.factories import CountryFactory
from releases.models import Release
from releases.tests.factories import (
    SongFactory,
    ReleaseFactory,
    CoverArtFactory,
    ReleaseArtistRoleFactory,
)
from releases.tests.factories import StoreFactory
from users.tests.factories import Artistv2Factory, UserFactory


@mock.patch("amuse.vendor.aws.sns.sns_send_message")
@mock.patch("amuse.tasks.zendesk_create_or_update_user")
def test_send_smart_link_creation_data_to_link_service(
    _zendesk_create_or_update_user_mock, aws_sns_send_message_mock
):
    with override_settings(AWS_SNS_SMART_LINK_TOPIC_ARN='arn:test'):
        expected_arn = 'arn:test'
        message_payload = [
            dict(
                type='album',
                amuse_release_id='mock-id',
                image='http://mock-url.com',
                artist_name='Test',
                name='Test',
            )
        ]
        send_smart_link_creation_data_to_link_service(message_payload)
        aws_sns_send_message_mock.assert_called_once_with(expected_arn, message_payload)


@mock.patch("amuse.tasks.save_cover_art_checksum")
@mock.patch("django.db.models.signals.ModelSignal.send")
@pytest.mark.django_db
def test_create_pre_release_smart_link_message_payload(_, __):
    mock_artist = Artistv2Factory.create(name='Test')
    mock_release = ReleaseFactory.create(
        type=2, stores=[StoreFactory(internal_name='apple', name='Apple')]
    )
    mock_song = SongFactory.create(release=mock_release)
    ReleaseArtistRoleFactory.create(release=mock_release, artist=mock_artist)
    cover_art = CoverArtFactory.create(release=mock_release)
    expected = dict(
        type='track',
        amuse_release_id=mock_release.id,
        song_id=str(mock_song.id),
        image=cover_art.thumbnail_url_400,
        artist_name=mock_artist.name,
        name=mock_release.name,
        include_pre_save_link=mock_release.include_pre_save_link,
        stores=SmartLinkStoreFlags.apple.value,
        status=mock_release.status,
    )
    result = create_pre_release_smart_link_message_payload(mock_release)
    assert result == expected


@pytest.mark.parametrize(
    'mock_release_type,expected_translated_type',
    [
        (Release.TYPE_EP, 'album'),
        (Release.TYPE_ALBUM, 'album'),
        (Release.TYPE_SINGLE, 'track'),
    ],
)
@mock.patch("django.db.models.signals.ModelSignal.send")
@pytest.mark.django_db
def test_translate_release_type_to_smart_link_service_type(
    _, mock_release_type, expected_translated_type
):
    release = ReleaseFactory(type=mock_release_type)
    result = translate_release_type_to_smart_link_service_type(release)
    assert result == expected_translated_type


@mock.patch("amuse.services.smart_link.email_smart_link_delivered_releases")
@mock.patch("django.db.models.signals.ModelSignal.send")
@pytest.mark.django_db
def test_amuse_smart_link_callback(_, mock_delivered_helper):
    mock_releases = ReleaseFactory.create_batch(size=20)
    mock_msg_batch = [
        {
            'type': 'track',
            'amuse_release_id': release.id,
            'link': f'https://share.amuse.io/track/{release.id}',
        }
        for release in mock_releases
    ]
    amuse_smart_link_callback(mock_msg_batch)
    for mock_release in mock_releases:
        mock_release.refresh_from_db()
        mock_link = f'https://share.amuse.io/track/{mock_release.id}'
        assert mock_release.link == mock_link

    release_ids = [r.id for r in mock_releases]
    mock_delivered_helper.assert_called_once_with(release_ids)


@mock.patch("amuse.tasks.save_cover_art_checksum")
@mock.patch("django.db.models.signals.ModelSignal.send")
@pytest.mark.django_db
def test_create_release_smart_link_message_payload_release_single_type(_, __):
    [CountryFactory(code=x) for x in ['US', 'SE', 'DE']]
    mock_artist = Artistv2Factory.create(name='Test')
    mock_release = ReleaseFactory.create(type=2)

    ReleaseArtistRoleFactory.create(release=mock_release, artist=mock_artist)
    cover_art = CoverArtFactory.create(release=mock_release)
    mock_song = SongFactory.create(release=mock_release)
    expected = dict(
        type='track',
        amuse_release_id=mock_release.id,
        song_id=str(mock_song.id),
        image=cover_art.thumbnail_url_400,
        artist_name=mock_artist.name,
        name=mock_release.name,
        upc=str(mock_release.upc),
        isrc=str(mock_song.isrc_code),
        countries_encoded=14,
        stores=0,
        status=mock_release.status,
    )
    result = create_release_smart_link_message_payload(mock_release)
    assert result == expected


@mock.patch("amuse.tasks.save_cover_art_checksum")
@mock.patch("django.db.models.signals.ModelSignal.send")
@pytest.mark.django_db
def test_create_release_smart_link_message_payload_release_album_type(_, __):
    mock_artist = Artistv2Factory.create(name='Test')
    mock_release = ReleaseFactory.create(type=1)
    ReleaseArtistRoleFactory.create(release=mock_release, artist=mock_artist)
    cover_art = CoverArtFactory.create(release=mock_release)
    expected = dict(
        type='album',
        amuse_release_id=mock_release.id,
        song_id=None,
        image=cover_art.thumbnail_url_400,
        artist_name=mock_artist.name,
        name=mock_release.name,
        upc=str(mock_release.upc),
        isrc=None,
        countries_encoded=0,
        stores=0,
        status=mock_release.status,
    )
    result = create_release_smart_link_message_payload(mock_release)
    assert result == expected


@mock.patch("django.db.models.signals.ModelSignal.send")
@pytest.mark.django_db
def test_smart_link_store_flags(_):
    release = ReleaseFactory(
        stores=[
            StoreFactory(name="Spotify", internal_name="spotify"),
            StoreFactory(name="Random Store", internal_name="random"),
            StoreFactory(name="Deezer", internal_name="deezer"),
        ]
    )

    internal_store_names = ['spotify', 'deezer', 'apple', 'youtube_music', 'tidal']
    smart_link_store_flag_names = SmartLinkStoreFlags.get_names()

    assert isinstance(smart_link_store_flag_names, list)
    assert len(internal_store_names) == len(smart_link_store_flag_names)
    assert (
        all(item in internal_store_names for item in smart_link_store_flag_names)
        is True
    )

    assert SmartLinkStoreFlags.get_none() is not None
    assert SmartLinkStoreFlags.get_none().value == 0

    release_store_flag = SmartLinkStoreFlags.get_release_flag(release)
    expected_release_store_flag = (
        SmartLinkStoreFlags.spotify | SmartLinkStoreFlags.deezer
    )
    assert expected_release_store_flag.value == release_store_flag


@mock.patch("amuse.services.smart_link.send_smart_link_delivered_email")
@mock.patch("django.db.models.signals.ModelSignal.send")
@pytest.mark.django_db
def test_email_smart_link_delivered_releases(_, mock_event):
    """Test that the event is triggered for both release.user and release.created_by"""
    owner = UserFactory()
    releases = ReleaseFactory.create_batch(
        size=20,
        status=Release.STATUS_DELIVERED,
        link="https://example.com/",
        created_by=owner,
    )
    release_ids = [r.id for r in releases]
    email_smart_link_delivered_releases(release_ids)
    assert mock_event.call_count == 40


@mock.patch("amuse.services.smart_link.send_smart_link_delivered_email")
@mock.patch("django.db.models.signals.ModelSignal.send")
@pytest.mark.django_db
def test_email_smart_link_delivered_releases_triggered_unique(_, mock_event):
    """Test that the event is only triggered once when release.user and release.created_by is the same User"""
    owner = UserFactory()
    release = ReleaseFactory(
        user=owner,
        created_by=owner,
        status=Release.STATUS_DELIVERED,
        link="https://example.com/",
    )
    email_smart_link_delivered_releases([release.id])
    assert mock_event.call_count == 1


@mock.patch("amuse.services.smart_link.send_smart_link_delivered_email")
@mock.patch("django.db.models.signals.ModelSignal.send")
@pytest.mark.django_db
def test_email_smart_link_delivered_releases_with_store_flags(_, mock_event):
    """Test that the event is triggered for both release.user and release.created_by"""
    owner = UserFactory()
    releases = ReleaseFactory.create_batch(
        size=20,
        status=Release.STATUS_DELIVERED,
        link="https://example.com/",
        created_by=owner,
        stores=[
            StoreFactory(internal_name='apple'),
            StoreFactory(internal_name='deezer'),
        ],
    )
    release_ids = [r.id for r in releases]
    email_smart_link_delivered_releases(release_ids)
    assert mock_event.call_count == 40


@mock.patch("django.db.models.signals.ModelSignal.send")
@pytest.mark.django_db
def test_create_store_flags_dict(_):
    release = ReleaseFactory(
        stores=[
            StoreFactory(name="Spotify", internal_name="spotify"),
            StoreFactory(name="Random Store", internal_name="random"),
            StoreFactory(name="Deezer", internal_name="deezer"),
        ]
    )

    expected_dict = {
        "spotify": True,
        "deezer": True,
        "apple": False,
        "youtube_music": False,
        "tidal": False,
    }

    store_flags_dict = SmartLinkStoreFlags.create_store_flags_dict(release)

    assert store_flags_dict == expected_dict
