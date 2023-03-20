import pytest
from unittest.mock import patch

from waffle.testutils import override_switch

from amuse.services.validation import validate, trigger_gcp_validation_service
from amuse.tasks import _calculate_django_file_checksum
from releases.models import SongArtistRole, SongFile
from releases.tests.factories import (
    CoverArtFactory,
    ReleaseFactory,
    ReleaseArtistRoleFactory,
    SongArtistRoleFactory,
    SongFactory,
    SongFileFactory,
)


@pytest.fixture
@patch("amuse.tasks.zendesk_create_or_update_user")
def test_release(_zendesk):
    release = ReleaseFactory()
    release_artist_role = ReleaseArtistRoleFactory(
        release=release, main_primary_artist=True
    )
    cover_art = CoverArtFactory(release=release)
    cover_art.checksum = _calculate_django_file_checksum(cover_art.file)
    cover_art.save()
    song = SongFactory(release=release)
    SongArtistRoleFactory(
        song=song,
        artist=release_artist_role.artist,
        role=SongArtistRole.ROLE_PRIMARY_ARTIST,
    )
    song_file = SongFileFactory(song=song, type=SongFile.TYPE_FLAC)
    return release


@pytest.mark.django_db
@patch("amuse.vendor.gcp.pubsub.PubSubClient.publish")
@patch("amuse.vendor.gcp.pubsub.PubSubClient.authenticate")
def test_trigger_gcp_validation_service(mock_auth, mock_publish, test_release):
    trigger_gcp_validation_service(test_release)
    mock_publish.assert_called_once()


@pytest.mark.django_db
@override_switch("service:validation:gcp", True)
@patch("amuse.services.validation.trigger_gcp_validation_service")
def test_validate_trigger_gcp_validation_service_enabled(mock_gcp, test_release):
    validate(test_release)
    mock_gcp.assert_called_once_with(test_release)


@pytest.mark.django_db
@override_switch("service:validation:gcp", False)
@patch("amuse.services.validation.trigger_gcp_validation_service")
def test_validate_trigger_gcp_validation_service_disabled(mock_gcp, test_release):
    validate(test_release)
    mock_gcp.assert_not_called()
