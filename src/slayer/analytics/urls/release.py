from django.urls import path

from slayer.analytics.views.release import (
    ReleaseSummaryView,
    ReleaseDailyView,
    ReleasePlaylistSummaryView,
    ReleaseCountrySummaryView,
    ReleaseTrackSummaryView,
    ReleaseMonthlyView,
    ReleaseShareView,
)

urlpatterns = [
    path(
        r'<int:artist_id>/release/<str:upc>/summary',
        ReleaseSummaryView.as_view(),
        name="release_summary",
    ),
    path(
        r'<int:artist_id>/release/<str:upc>/daily',
        ReleaseDailyView.as_view(),
        name="release_daily",
    ),
    path(
        r'<int:artist_id>/release/<str:upc>/playlists',
        ReleasePlaylistSummaryView.as_view(),
        name="release_playlists",
    ),
    path(
        r'<int:artist_id>/release/<str:upc>/countries',
        ReleaseCountrySummaryView.as_view(),
        name="release_countries",
    ),
    path(
        r'<int:artist_id>/release/<str:upc>/tracks',
        ReleaseTrackSummaryView.as_view(),
        name="release_tracks",
    ),
    path(
        r'<int:artist_id>/release/<str:upc>/monthly',
        ReleaseMonthlyView.as_view(),
        name="release_monthly",
    ),
    path(
        r'<int:artist_id>/release/<str:upc>/share',
        ReleaseShareView.as_view(),
        name="release_share",
    ),
]
