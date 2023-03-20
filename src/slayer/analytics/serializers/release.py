from .enrichers.release import (
    ReleaseMetaEnricher,
    ReleaseartistMetaEnricher,
    ReleasePlaylistTrackEnricher,
    ReleaseTrackEnricher,
)
from .adapters.release import (
    ReleaseDailyDataclassAdapter,
    ReleasePlaylistDataclassAdapter,
    ReleaseSummaryDataclassAdapter,
    ReleaseTrackDataclassAdapter,
    ReleaseCountryDataclassAdapter,
    ReleaseMonthlyDataclassAdapter,
    ReleaseShareDataclassAdapter,
)


class ReleaseCountrySerializer(ReleaseCountryDataclassAdapter, ReleaseMetaEnricher):
    pass


class ReleaseDailySerializer(ReleaseDailyDataclassAdapter, ReleaseMetaEnricher):
    pass


class ReleasePlaylistSerializer(
    ReleasePlaylistDataclassAdapter,
    ReleaseMetaEnricher,
    ReleasePlaylistTrackEnricher,
):
    pass


class ReleaseSummarySerializer(
    ReleaseSummaryDataclassAdapter, ReleaseartistMetaEnricher
):
    pass


class ReleaseTrackSerializer(ReleaseTrackDataclassAdapter, ReleaseTrackEnricher):
    pass


class ReleaseMonthlySerializer(ReleaseMonthlyDataclassAdapter, ReleaseMetaEnricher):
    pass


class ReleaseShareSerializer(ReleaseShareDataclassAdapter, ReleaseMetaEnricher):
    pass
