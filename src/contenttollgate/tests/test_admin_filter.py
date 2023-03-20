from django.test import TestCase

from contenttollgate.admin_filter import (
    generate_spotify_url_from_uri,
    has_multiple_warnings,
    get_track_duration,
)


class GenerateSpotifyUrlTest(TestCase):
    def test_generates_url_correctly(self):
        uri = "spotify:track:test12345"
        url = generate_spotify_url_from_uri(uri)
        assert url == "https://open.spotify.com/track/test12345"

    def test_return_empty_string_when_incorrect_uri_given(self):
        uri = "this_is_not_a_spotify_uri"
        url = generate_spotify_url_from_uri(uri)
        assert url == ""


class HasMultipleWarningsTest(TestCase):
    def test_true_if_multiple_warnings(self):
        warnings = [
            {"track_id": 1, "show_warning": True},
            {"track_id": 2, "show_warning": True},
        ]
        assert has_multiple_warnings(warnings) is True

    def test_false_if_not_multiple_shown_warnings(self):
        warnings = [
            {"track_id": 1, "show_warning": True},
            {"track_id": 2, "show_warning": False},
        ]
        assert has_multiple_warnings(warnings) is False

    def test_false_if_not_multiple_with_track_id(self):
        warnings = [
            {"track_id": 1, "show_warning": True},
            {"release_id": 1, "show_warning": True},
        ]
        assert has_multiple_warnings(warnings) is False


class GetTrackDurationTest(TestCase):
    def test_correctly_casts_ms_to_MMSS(self):
        result = {'duration_ms': 205000}
        assert get_track_duration(result) == "3:25"
