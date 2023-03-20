from rest_framework_dataclasses.serializers import DataclassSerializer
from pyslayer.services import analytics


class TrackCountryDataclassAdapter(DataclassSerializer):
    class Request(DataclassSerializer):
        class Meta:
            dataclass = analytics.ArtistTrackCountrySummaryRequest

    class Meta:
        dataclass = analytics.ArtistTrackCountrySummaryResponse


class TrackDailyDataclassAdapter(DataclassSerializer):
    class Request(DataclassSerializer):
        class Meta:
            dataclass = analytics.ArtistTrackDailyRequest

    class Meta:
        dataclass = analytics.ArtistTrackDailyResponse


class TrackUGCDailyDataclassAdapter(DataclassSerializer):
    class Request(DataclassSerializer):
        class Meta:
            dataclass = analytics.ArtistTrackUgcDailyRequest

    class Meta:
        dataclass = analytics.ArtistTrackUgcDailyResponse


class TrackYTCIDSummaryDataclassAdapter(DataclassSerializer):
    class Request(DataclassSerializer):
        class Meta:
            dataclass = analytics.ArtistTrackYoutubeContentIdSummaryRequest

    class Meta:
        dataclass = analytics.ArtistTrackYoutubeContentIdSummaryResponse


class TrackPlaylistDataclassAdapter(DataclassSerializer):
    class Request(DataclassSerializer):
        class Meta:
            dataclass = analytics.ArtistTrackPlaylistSummaryRequest

    class Meta:
        dataclass = analytics.ArtistTrackPlaylistSummaryResponse


class TrackSummaryDataclassAdapter(DataclassSerializer):
    class Request(DataclassSerializer):
        class Meta:
            dataclass = analytics.TrackSummaryRequest

    class Meta:
        dataclass = analytics.TrackSummaryResponse


class TrackMonthlyDataclassAdapter(DataclassSerializer):
    class Request(DataclassSerializer):
        class Meta:
            dataclass = analytics.ArtistTrackMonthlyRequest

    class Meta:
        dataclass = analytics.ArtistTrackMonthlyResponse
