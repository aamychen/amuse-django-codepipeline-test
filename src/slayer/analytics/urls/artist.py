from django.urls import path

from slayer.analytics.views.artist import (
    ArtistSummaryView,
    ArtistDailyView,
    ArtistTrackSummaryView,
    ArtistPlaylistSummaryView,
    ArtistCountrySummaryView,
    ArtistReleaseSummaryView,
    ArtistMonthlyView,
)

urlpatterns = [
    path(
        r'<int:artist_id>/summary', ArtistSummaryView.as_view(), name="artist_summary"
    ),
    path(r'<int:artist_id>/daily', ArtistDailyView.as_view(), name="artist_daily"),
    path(
        r'<int:artist_id>/tracks',
        ArtistTrackSummaryView.as_view(),
        name="artist_tracks",
    ),
    path(
        r'<int:artist_id>/releases',
        ArtistReleaseSummaryView.as_view(),
        name="artist_releases",
    ),
    path(
        r'<int:artist_id>/playlists',
        ArtistPlaylistSummaryView.as_view(),
        name="artist_playlists",
    ),
    path(
        r'<int:artist_id>/countries',
        ArtistCountrySummaryView.as_view(),
        name="artist_countries",
    ),
    path(
        r'<int:artist_id>/monthly',
        ArtistMonthlyView.as_view(),
        name="artist_monthly",
    ),
]
