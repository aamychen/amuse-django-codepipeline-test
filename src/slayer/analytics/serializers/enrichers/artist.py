from amuse.logging import logger
from users.models import ArtistV2
from rest_framework.serializers import Serializer, CharField

from .base import BaseEnricher


class ArtistMetadataSerializer(Serializer):
    name = CharField(required=False)
    image = CharField(allow_null=True, required=False)


class ReleaseSummaryEnricher(BaseEnricher):
    def enrich(self, context):
        super().enrich(context)
        if releases := self.initial_data.get("artist_release_summaries"):
            self.enrich_releasedata(releases)


class ArtistMetaEnricher(BaseEnricher):
    artist_metadata = ArtistMetadataSerializer(required=False)

    def enrich(self, context):
        super().enrich(context)
        artist_id = context["artist_id"]
        try:
            self.initial_data["artist_metadata"] = self.get_artist_metadata(artist_id)
        except ArtistV2.DoesNotExist:
            logger.warning(f"Error getting artist by id: {artist_id}")
            raise


class ArtistTrackSummaryEnricher(BaseEnricher):
    def enrich(self, context):
        super().enrich(context)
        if tracks := self.initial_data.get("artist_track_summaries"):
            self.enrich_tracks(tracks)


class PlaylistCollectionEnricher(BaseEnricher):
    def enrich(self, context):
        super().enrich(context)
        self.enrich_tracks(self.initial_data["playlist_summary"]["playlists"])


class LatestReleaseEnricher(BaseEnricher):
    def enrich(self, context):
        super().enrich(context)
        self.initial_data["latest_release"] = self.get_latest_release(
            context["artist_id"]
        )
