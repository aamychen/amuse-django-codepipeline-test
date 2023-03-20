from .enrichers.artist import (
    LatestReleaseEnricher,
    ArtistMetaEnricher,
    ReleaseSummaryEnricher,
    ArtistTrackSummaryEnricher,
    PlaylistCollectionEnricher,
)
from .adapters.artist import (
    ArtistReleaseDataclassAdapter,
    ArtistSummaryDataclassAdapter,
    ArtistTrackDataclassAdapter,
    ArtistCountryDataclassAdapter,
    ArtistDailyDataclassAdapter,
    ArtistPlaylistDataclassAdapter,
    ArtistMonthlyDataclassAdapter,
)


class ArtistReleaseSerializer(
    ArtistReleaseDataclassAdapter,
    ArtistMetaEnricher,
    ReleaseSummaryEnricher,
    LatestReleaseEnricher,
):
    pass


class ArtistCountrySerializer(ArtistCountryDataclassAdapter, ArtistMetaEnricher):
    pass


class ArtistDailySerializer(ArtistDailyDataclassAdapter, ArtistMetaEnricher):
    pass


class ArtistPlaylistSerializer(
    ArtistPlaylistDataclassAdapter, ArtistMetaEnricher, PlaylistCollectionEnricher
):
    pass


class ArtistSummarySerializer(ArtistSummaryDataclassAdapter, ArtistMetaEnricher):
    pass


class ArtistTrackSerializer(
    ArtistTrackDataclassAdapter, ArtistMetaEnricher, ArtistTrackSummaryEnricher
):
    pass


class ArtistMonthlySerializer(ArtistMonthlyDataclassAdapter, ArtistMetaEnricher):
    pass
