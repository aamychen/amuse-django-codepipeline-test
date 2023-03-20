from rest_framework_dataclasses.serializers import DataclassSerializer
from pyslayer.services import analytics


class ArtistReleaseDataclassAdapter(DataclassSerializer):
    class Request(DataclassSerializer):
        class Meta:
            dataclass = analytics.ArtistReleaseSummaryRequest

    class Meta:
        dataclass = analytics.ArtistReleaseSummaryResponse


class ArtistCountryDataclassAdapter(DataclassSerializer):
    class Request(DataclassSerializer):
        class Meta:
            dataclass = analytics.ArtistCountrySummaryRequest

    class Meta:
        dataclass = analytics.ArtistCountrySummaryResponse


class ArtistDailyDataclassAdapter(DataclassSerializer):
    class Request(DataclassSerializer):
        class Meta:
            dataclass = analytics.ArtistDailyRequest

    class Meta:
        dataclass = analytics.ArtistDailyResponse


class ArtistPlaylistDataclassAdapter(DataclassSerializer):
    class Request(DataclassSerializer):
        class Meta:
            dataclass = analytics.ArtistPlaylistSummaryRequest

    class Meta:
        dataclass = analytics.ArtistPlaylistSummaryResponse


class ArtistSummaryDataclassAdapter(DataclassSerializer):
    class Request(DataclassSerializer):
        class Meta:
            dataclass = analytics.ArtistSummaryRequest

    class Meta:
        dataclass = analytics.ArtistSummaryResponse


class ArtistTrackDataclassAdapter(DataclassSerializer):
    class Request(DataclassSerializer):
        class Meta:
            dataclass = analytics.ArtistTrackSummaryRequest

    class Meta:
        dataclass = analytics.ArtistTrackSummaryResponse


class ArtistMonthlyDataclassAdapter(DataclassSerializer):
    class Request(DataclassSerializer):
        class Meta:
            dataclass = analytics.ArtistMonthlyRequest

    class Meta:
        dataclass = analytics.ArtistMonthlyResponse
