import pytest
import responses
from unittest import mock

from django.test import override_settings

from amuse.vendor.release_analysis.api import (
    get_results,
    ReleaseAnalysisApiError,
    format_response,
)


@override_settings(GCP_SERVICE_ACCOUNT_JSON=None, RELEASE_ANALYSIS_CLIENT_ID="test")
def test_throws_exception_when_service_account_credentials_missing():
    with pytest.raises(ValueError):
        get_results(123)


@override_settings(GCP_SERVICE_ACCOUNT_JSON="test", RELEASE_ANALYSIS_CLIENT_ID=None)
def test_throws_exception_when_release_analysis_client_id_missing():
    with pytest.raises(ValueError):
        get_results(123)


@responses.activate
@mock.patch('amuse.vendor.release_analysis.api.generate_token')
def test_returns_api_response(_):
    release_id = 123
    expected_response = {
        "has_warning": True,
        "profanity_warnings": [],
        "silence_warnings": [],
        "acr_cloud_warnings": [],
        "tracks": {},
        "tracks_with_warnings": [],
        'tracks_with_critical_warnings': [],
    }

    responses.add(
        responses.GET,
        f"https://release-analysis.amuse.io/warnings/release/{release_id}",
        json=expected_response,
        status=200,
    )

    assert get_results(release_id) == expected_response


@responses.activate
@mock.patch('amuse.vendor.release_analysis.api.generate_token')
def test_throws_exception_when_403_response(_):
    release_id = 123
    expected_response = {"has_warning": True}

    responses.add(
        responses.GET,
        f"https://release-analysis.amuse.io/warnings/release/{release_id}",
        json=expected_response,
        status=403,
    )
    with pytest.raises(ReleaseAnalysisApiError):
        get_results(release_id)


@responses.activate
@mock.patch('amuse.vendor.release_analysis.api.generate_token')
def test_throws_exception_when_non_200_response(_):
    release_id = 123
    expected_response = {"has_warning": True}

    responses.add(
        responses.GET,
        f"https://release-analysis.amuse.io/warnings/release/{release_id}",
        json=expected_response,
        status=404,
    )
    with pytest.raises(ReleaseAnalysisApiError):
        get_results(release_id)


def test_format_response_orders_acr_matches_correctly():
    track_id = 4485398
    acr_matches = [
        generate_acr_cloud_warning_match(90, "song_2", "Indie Distro"),
        generate_acr_cloud_warning_match(20, "song_1", "bastille"),
        generate_acr_cloud_warning_match(75, "song_3", "Sony Music"),
    ]
    api_response = build_mock_release_analysis_service_response(track_id, acr_matches)

    format_response(api_response)
    assert (
        api_response["acr_cloud_warnings"][0]['acr_cloud_warning_matches'][0]['score']
        == 75.0
    )
    assert (
        api_response["acr_cloud_warnings"][0]['acr_cloud_warning_matches'][0][
            'acr_cloud_track_id'
        ]
        == "song_3"
    )
    assert (
        api_response["acr_cloud_warnings"][0]['acr_cloud_warning_matches'][0][
            'is_major_label_distributor'
        ]
        == True
    )

    assert (
        api_response["acr_cloud_warnings"][0]['acr_cloud_warning_matches'][1][
            'acr_cloud_track_id'
        ]
        == "song_1"
    )
    assert (
        api_response["acr_cloud_warnings"][0]['acr_cloud_warning_matches'][1]['score']
        == 20.0
    )
    assert (
        api_response["acr_cloud_warnings"][0]['acr_cloud_warning_matches'][1][
            'is_major_label_distributor'
        ]
        == True
    )

    assert (
        api_response["acr_cloud_warnings"][0]['acr_cloud_warning_matches'][2]['score']
        == 90.0
    )
    assert (
        api_response["acr_cloud_warnings"][0]['acr_cloud_warning_matches'][2][
            'acr_cloud_track_id'
        ]
        == "song_2"
    )
    assert (
        api_response["acr_cloud_warnings"][0]['acr_cloud_warning_matches'][2][
            'is_major_label_distributor'
        ]
        == False
    )
    assert api_response["tracks"][track_id] == api_response["acr_cloud_warnings"]
    assert api_response["tracks_with_warnings"] == [track_id]
    assert api_response["tracks_with_critical_warnings"] == [track_id]


def test_format_response_orders_sets_tracks_with_warnings_correctly_no_warnings():
    track_id = 12342
    acr_matches = [generate_acr_cloud_warning_match(60, "song_1", "Indie Distro")]
    show_warning = False
    api_response = build_mock_release_analysis_service_response(
        track_id, acr_matches, show_warning
    )

    format_response(api_response)
    assert api_response["tracks_with_warnings"] == []
    assert api_response["tracks_with_critical_warnings"] == []


def test_format_response_orders_sets_tracks_with_warnings_correctly_no_critical_warnings():
    track_id = 12343
    acr_matches = [generate_acr_cloud_warning_match(80, "song_1", "Indie Distro")]
    show_warning = False
    api_response = build_mock_release_analysis_service_response(
        track_id, acr_matches, show_warning
    )

    format_response(api_response)

    assert api_response["tracks_with_critical_warnings"] == []
    assert api_response["tracks_with_warnings"] == [track_id]


def test_format_response_orders_sets_tracks_with_warnings_correctly_critical_warnings():
    track_id = 12344
    acr_matches = [generate_acr_cloud_warning_match(91, "song_1", "Sony Music")]
    show_warning = True
    api_response = build_mock_release_analysis_service_response(
        track_id, acr_matches, show_warning
    )

    format_response(api_response)

    assert api_response["tracks_with_critical_warnings"] == [track_id]
    assert api_response["tracks_with_warnings"] == [track_id]


def build_mock_release_analysis_service_response(
    track_id, acr_matches, show_warning=True
):
    return {
        "has_warning": True,
        "spotify_watchlist_warnings": [],
        "amuse_watchlist_warnings": [],
        "profanity_warnings": [],
        "apple_store_warnings": [],
        "suspect_metadata_warnings": [],
        "silence_detection_warnings": [],
        "acr_cloud_warnings": [
            {
                "release_id": 1936318,
                "track_id": track_id,
                "event_id": "",
                "trigger": "TrackAudioACRCloud()",
                "result_type": "[]*ACRCloudResult",
                "result_version": "0.0.1",
                "show_warning": show_warning,
                "acr_cloud_warning_matches": acr_matches,
            }
        ],
    }


def generate_acr_cloud_warning_match(score, name, content_provider):
    return {
        "acr_cloud_track_id": name,
        "major_label_match": True,
        "multi_segment_match": False,
        "acr_cloud_results": [
            {
                "release_id": 123,
                "track_id": 1,
                "user_id": 0,
                "start_ms": 90000,
                "end_ms": 100000,
                "segment_offset": 3,
                "score": score,
                "spotify_track_uri": "spotify:track:uri",
                "release_date": "2020-09-18",
                "result": {
                    "db_begin_time_offset_ms": 0,
                    "db_end_time_offset_ms": 0,
                    "sample_begin_time_offset_ms": 0,
                    "sample_end_time_offset_ms": 0,
                    "play_offset_ms": 15700,
                    "artists": [],
                    "acrid": "cf98d6cef58294c77bb4e120a2c829df",
                    "album": {"name": name},
                    "external_ids": {
                        "iswc": "",
                        "isrc": "ISRC123123",
                        "upc": "UPC123123123",
                    },
                    "result_from": 3,
                    "title": name,
                    "language": "",
                    "duration_ms": 136000,
                },
                "apple_store_matches": [
                    {
                        "collection": {
                            "collection_id": f"apple-id-{name}",
                            "name": name,
                            "artist_display_name": "test artist",
                            "view_url": "https://itunes.apple.com/album/test",
                            "artwork_url": "https://a-url.com",
                            "original_release_date": {"seconds": 1600387200},
                            "itunes_release_date": {"seconds": 1599696000},
                            "label_studio": "Test",
                            "content_provider_name": content_provider,
                            "copyright": "℗ 2020 test",
                            "p_line": "2020 test",
                        },
                        "track_number": 10,
                        "volume_number": 1,
                        "song": {
                            "song_id": 123,
                            "name": "test_song",
                            "artist_display_name": "Lux-Inspira",
                            "isrc": "TESTISRC",
                            "original_release_date": {"seconds": 1600387200},
                            "itunes_release_date": {"seconds": 1599696000},
                            "copyright": "℗ 2020 Test",
                            "p_line": "2020 Test",
                        },
                    }
                ],
                "is_warning": True,
            }
        ],
    }
