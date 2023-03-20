from .base import BaseEnricher


class TrackMetaEnricher(BaseEnricher):
    def enrich(self, context):
        super(TrackMetaEnricher, self).enrich(context)
        self.initial_data["track_metadata"] = self.get_enriched_track(context["isrc"])


class TrackPlaylistTrackEnricher(BaseEnricher):
    def enrich(self, context):
        super().enrich(context)
        self.enrich_tracks(self.initial_data["playlist_summary"]["playlists"])
