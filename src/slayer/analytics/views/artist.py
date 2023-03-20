from slayer.analytics.serializers.artist import (
    ArtistCountrySerializer,
    ArtistDailySerializer,
    ArtistPlaylistSerializer,
    ArtistReleaseSerializer,
    ArtistSummarySerializer,
    ArtistTrackSerializer,
    ArtistMonthlySerializer,
)
from slayer.clientwrapper import slayer
from .base import AnalyticsArtistView


class ArtistCountrySummaryView(AnalyticsArtistView):
    serializer_class = ArtistCountrySerializer
    slayer_fn = slayer.analytics_artist_country_summary


class ArtistDailyView(AnalyticsArtistView):
    serializer_class = ArtistDailySerializer
    slayer_fn = slayer.analytics_artist_daily


class ArtistPlaylistSummaryView(AnalyticsArtistView):
    serializer_class = ArtistPlaylistSerializer
    slayer_fn = slayer.analytics_artist_playlist_summary


class ArtistReleaseSummaryView(AnalyticsArtistView):
    serializer_class = ArtistReleaseSerializer
    slayer_fn = slayer.analytics_artist_release_summary


class ArtistSummaryView(AnalyticsArtistView):
    serializer_class = ArtistSummarySerializer
    slayer_fn = slayer.analytics_artist_summary


class ArtistTrackSummaryView(AnalyticsArtistView):
    serializer_class = ArtistTrackSerializer
    slayer_fn = slayer.analytics_artist_track_summary


class ArtistMonthlyView(AnalyticsArtistView):
    serializer_class = ArtistMonthlySerializer
    slayer_fn = slayer.analytics_monthly
