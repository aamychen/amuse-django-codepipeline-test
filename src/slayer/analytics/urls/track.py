from django.urls import path

from slayer.analytics.views.track import (
    TrackSummaryView,
    TrackDailyView,
    TrackPlaylistSummaryView,
    TrackCountrySummaryView,
    TrackMonthlyView,
    TrackUGCDailyView,
    TrackYTCIDSummaryView,
)

urlpatterns = [
    path(
        r'<int:artist_id>/track/<str:isrc>/summary',
        TrackSummaryView.as_view(),
        name="track_summary",
    ),
    path(
        r'<int:artist_id>/track/<str:isrc>/daily',
        TrackDailyView.as_view(),
        name="track_daily",
    ),
    path(
        r'<int:artist_id>/track/<str:isrc>/ugc/daily',
        TrackUGCDailyView.as_view(),
        name="track_ugc_daily",
    ),
    path(
        r'<int:artist_id>/track/<str:isrc>/ugc/cid/summary',
        TrackYTCIDSummaryView.as_view(),
        name="track_yt_cid_summary",
    ),
    path(
        r'<int:artist_id>/track/<str:isrc>/playlists',
        TrackPlaylistSummaryView.as_view(),
        name="track_playlist",
    ),
    path(
        r'<int:artist_id>/track/<str:isrc>/countries',
        TrackCountrySummaryView.as_view(),
        name="track_countries",
    ),
    path(
        r'<int:artist_id>/track/<str:isrc>/monthly',
        TrackMonthlyView.as_view(),
        name="track_monthly",
    ),
]
