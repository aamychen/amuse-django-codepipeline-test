from slayer.analytics.serializers.release import (
    ReleaseCountrySerializer,
    ReleaseDailySerializer,
    ReleasePlaylistSerializer,
    ReleaseSummarySerializer,
    ReleaseTrackSerializer,
    ReleaseMonthlySerializer,
    ReleaseShareSerializer,
)
from slayer.clientwrapper import slayer
from .base import AnalyticsReleaseView


class ReleaseCountrySummaryView(AnalyticsReleaseView):
    serializer_class = ReleaseCountrySerializer
    slayer_fn = slayer.analytics_release_countries


class ReleaseDailyView(AnalyticsReleaseView):
    serializer_class = ReleaseDailySerializer
    slayer_fn = slayer.analytics_release_daily


class ReleasePlaylistSummaryView(AnalyticsReleaseView):
    serializer_class = ReleasePlaylistSerializer
    slayer_fn = slayer.analytics_release_playlist


class ReleaseSummaryView(AnalyticsReleaseView):
    serializer_class = ReleaseSummarySerializer
    slayer_fn = slayer.analytics_release_summary


class ReleaseTrackSummaryView(AnalyticsReleaseView):
    serializer_class = ReleaseTrackSerializer
    slayer_fn = slayer.analytics_artist_release_tracks


class ReleaseMonthlyView(AnalyticsReleaseView):
    serializer_class = ReleaseMonthlySerializer
    slayer_fn = slayer.analytics_release_monthly


class ReleaseShareView(AnalyticsReleaseView):
    serializer_class = ReleaseShareSerializer
    slayer_fn = slayer.analytics_release_share
