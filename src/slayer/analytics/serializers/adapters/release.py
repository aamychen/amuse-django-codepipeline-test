from rest_framework_dataclasses.serializers import DataclassSerializer
from pyslayer.services import analytics


class ReleaseCountryDataclassAdapter(DataclassSerializer):
    class Request(DataclassSerializer):
        class Meta:
            dataclass = analytics.ArtistReleaseCountrySummaryRequest

    class Meta:
        dataclass = analytics.ArtistReleaseCountrySummaryResponse


class ReleaseDailyDataclassAdapter(DataclassSerializer):
    class Request(DataclassSerializer):
        class Meta:
            dataclass = analytics.ArtistReleaseDailyRequest

    class Meta:
        dataclass = analytics.ArtistReleaseDailyResponse


class ReleasePlaylistDataclassAdapter(DataclassSerializer):
    class Request(DataclassSerializer):
        class Meta:
            dataclass = analytics.ArtistReleasePlaylistSummaryRequest

    class Meta:
        dataclass = analytics.ArtistReleasePlaylistSummaryResponse


class ReleaseSummaryDataclassAdapter(DataclassSerializer):
    class Request(DataclassSerializer):
        class Meta:
            dataclass = analytics.ReleaseSummaryRequest

    class Meta:
        dataclass = analytics.ReleaseSummaryResponse


class ReleaseTrackDataclassAdapter(DataclassSerializer):
    class Request(DataclassSerializer):
        class Meta:
            dataclass = analytics.ArtistReleaseTrackSummaryRequest

    class Meta:
        dataclass = analytics.ArtistReleaseTrackSummaryResponse


class ReleaseMonthlyDataclassAdapter(DataclassSerializer):
    class Request(DataclassSerializer):
        class Meta:
            dataclass = analytics.ArtistReleaseMonthlyRequest

    class Meta:
        dataclass = analytics.ArtistReleaseMonthlyResponse


class ReleaseShareDataclassAdapter(DataclassSerializer):
    class Request(DataclassSerializer):
        class Meta:
            dataclass = analytics.ArtistReleaseShareRequest

    class Meta:
        dataclass = analytics.ArtistReleaseShareResponse
