from slayer.analytics.serializers.track import (
    TrackSummarySerializer,
    TrackDailySerializer,
    TrackPlaylistSerializer,
    TrackCountrySerializer,
    TrackMonthlySerializer,
    TrackUGCDailySerializer,
    TrackYTCIDSummarySerializer,
)
from slayer.clientwrapper import slayer
from .base import AnalyticsTrackView


class TrackCountrySummaryView(AnalyticsTrackView):
    serializer_class = TrackCountrySerializer
    slayer_fn = slayer.analytics_track_countries


class TrackDailyView(AnalyticsTrackView):
    serializer_class = TrackDailySerializer
    slayer_fn = slayer.analytics_track_daily


class TrackUGCDailyView(AnalyticsTrackView):
    serializer_class = TrackUGCDailySerializer
    slayer_fn = slayer.analytics_track_ugc_daily


class TrackYTCIDSummaryView(AnalyticsTrackView):
    serializer_class = TrackYTCIDSummarySerializer
    slayer_fn = slayer.analytics_track_yt_cid_summary


class TrackPlaylistSummaryView(AnalyticsTrackView):
    serializer_class = TrackPlaylistSerializer
    slayer_fn = slayer.analytics_track_playlist


class TrackSummaryView(AnalyticsTrackView):
    serializer_class = TrackSummarySerializer
    slayer_fn = slayer.analytics_track_summary


class TrackMonthlyView(AnalyticsTrackView):
    serializer_class = TrackMonthlySerializer
    slayer_fn = slayer.analytics_track_monthly
