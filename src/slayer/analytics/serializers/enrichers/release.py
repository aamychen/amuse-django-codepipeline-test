from .base import BaseEnricher


class ReleaseMetaEnricher(BaseEnricher):
    def enrich(self, context):
        super().enrich(context)
        self.initial_data["release_metadata"] = self.enrich_release(context["upc"])


class ReleaseSummaryEnricher(BaseEnricher):
    def enrich(self, context):
        super().enrich(context)
        if releases := self.initial_data.get("artist_release_summaries"):
            self.enrich_releasedata(releases)


class ReleaseartistMetaEnricher(BaseEnricher):
    def enrich(self, context):
        super().enrich(context)
        self.initial_data["releaseartist_metadata"] = self.enrich_release(
            context["upc"]
        )


class ReleasePlaylistTrackEnricher(BaseEnricher):
    def enrich(self, context):
        super().enrich(context)
        self.enrich_tracks(self.initial_data["playlist_summary"]["playlists"])


class ReleaseTrackEnricher(BaseEnricher):
    def enrich(self, context):
        super().enrich(context)
        self.enrich_tracks(self.initial_data["artist_release_track_summaries"])
