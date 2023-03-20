from .enrichers.track import (
    TrackMetaEnricher,
    TrackPlaylistTrackEnricher,
)
from .adapters.track import (
    TrackCountryDataclassAdapter,
    TrackDailyDataclassAdapter,
    TrackPlaylistDataclassAdapter,
    TrackSummaryDataclassAdapter,
    TrackMonthlyDataclassAdapter,
    TrackUGCDailyDataclassAdapter,
    TrackYTCIDSummaryDataclassAdapter,
)


class TrackSummarySerializer(TrackSummaryDataclassAdapter, TrackMetaEnricher):
    pass


class TrackDailySerializer(TrackDailyDataclassAdapter, TrackMetaEnricher):
    pass


class TrackUGCDailySerializer(TrackUGCDailyDataclassAdapter, TrackMetaEnricher):
    pass


class TrackYTCIDSummarySerializer(TrackYTCIDSummaryDataclassAdapter, TrackMetaEnricher):
    pass


class TrackPlaylistSerializer(
    TrackPlaylistDataclassAdapter, TrackMetaEnricher, TrackPlaylistTrackEnricher
):
    pass


class TrackCountrySerializer(TrackCountryDataclassAdapter, TrackMetaEnricher):
    pass


class TrackMonthlySerializer(TrackMonthlyDataclassAdapter, TrackMetaEnricher):
    pass
