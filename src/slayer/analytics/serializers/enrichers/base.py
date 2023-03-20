from collections import deque

from django.db.models import Q

from slayer.clientwrapper import slayer
from amuse.logging import logger
from users.models import ArtistV2
from releases.models import ReleaseArtistRole, SongArtistRole, Release, Song
from pyslayer.services.analytics import ReleaseSummaryRequest
from pyslayer.utils import to_dict
from rest_framework.serializers import Serializer
from codes.models import FAKE_UPC


class BaseEnricher(Serializer):
    def enrich(self, context):
        pass

    def get_artist_metadata(self, artist_id):
        artist = ArtistV2.objects.get(id=artist_id)
        return {"name": artist.name, "image": artist.image}

    def get_latest_release(self, artist_id):
        try:
            query = Q(status__in=[Release.STATUS_RELEASED, Release.STATUS_TAKEDOWN])

            # Skip releases missing UPC
            query.add(Q(upc_id__isnull=False), Q.AND)

            # Query for releases by owner/contributor
            query.add(
                Q(
                    id__in=ReleaseArtistRole.objects.filter(artist_id=artist_id).values(
                        "release"
                    )
                )
                | Q(
                    id__in=SongArtistRole.objects.filter(artist_id=artist_id).values(
                        "song__release"
                    )
                ),
                Q.AND,
            )

            # Execute query
            latest_release = Release.objects.filter(query).order_by("-id").first()

            if not latest_release:
                return {}

            # Build latest_release object
            response = slayer.analytics_release_summary(
                artist_id=artist_id, upc=latest_release.upc.code
            )

            response["release_metadata"] = {
                "name": latest_release.name,
                "version": latest_release.release_version,
                "release_date": latest_release.release_date.strftime("%Y-%m-%d")
                if latest_release.release_date
                else None,
                "cover_art": latest_release.cover_art.thumbnail_url_400,
            }

            return response

        except Exception as e:
            logger.exception(e)
            return {}

    def enrich_release(self, upc):
        """Returns a release metadata object for given UPC (not to be used in loops for
        efficiency reasons, (gets really slow compared to the collection version)"""

        release = (
            Release.objects.select_related("upc")
            .select_related("cover_art")
            .filter(upc__code=upc)
            .order_by("-id")
            .first()
        )

        return (
            dict(
                name=release.name,
                version=release.release_version,
                release_date=release.release_date.strftime("%Y-%m-%d")
                if release.release_date
                else None,
                cover_art=release.cover_art.thumbnail_url_400,
            )
            if release
            else {}
        )

    def get_enriched_releases(self, releases_upcs):
        """Yields enriched release metadata for the given upcs"""

        r_upc_map = dict(releases_upcs)
        q_releases = deque(r_upc_map.keys())

        releases = (
            Release.objects.select_related("upc")
            .select_related("cover_art")
            .filter(upc__code__in=set(r_upc_map.values()))
        )

        # Iterate over release metadata obtained from database
        for r in releases.all():
            # Iterate over the track indices queue
            for idx in list(q_releases):
                if r.upc.code != r_upc_map[idx]:
                    continue

                # Pop enrichment-eligible index from queue to make things efficient
                q_releases.remove(idx)

                # Yield the enriched object with reference to the release
                yield idx, dict(
                    name=r.name,
                    version=r.release_version,
                    release_date=r.release_date.strftime("%Y-%m-%d")
                    if r.release_date
                    else None,
                    cover_art=r.cover_art.thumbnail_url_400,
                )

    def get_enriched_track(self, isrc):
        """Returns a track metadata object for given ISRC (not to be used in loops for
        efficiency reasons, (gets really slow compared to the collection version)"""

        track = (
            Song.objects.select_related("isrc")
            .select_related("release")
            .select_related("release__cover_art")
            .filter(isrc__code=isrc)
            .order_by("-id")
            .first()
        )

        return (
            dict(
                name=track.name,
                version=track.version,
                release_date=track.release.release_date.strftime("%Y-%m-%d")
                if track.release.release_date
                else None,
                cover_art=track.release.cover_art.thumbnail_url_400,
            )
            if track
            else {}
        )

    def get_enriched_tracks(self, isrcs):
        """Returns a generator yielding track metadata for the given track-isrc pairs"""

        t_isrc_map = dict(isrcs)
        q_tracks = deque(t_isrc_map.keys())

        tracks = (
            Song.objects.select_related("isrc")
            .select_related("release")
            .select_related("release__cover_art")
            .filter(isrc__code__in=set(t_isrc_map.values()))
        )

        # Iterate over track metadata obtained from database
        for t in tracks.all():
            # Iterate over the track indices queue
            for idx in list(q_tracks):
                if t.isrc.code != t_isrc_map[idx]:
                    continue

                # Pop enrichment-eligible index from queue to make things efficient
                q_tracks.remove(idx)

                # Yield the enriched object with reference to the track
                yield idx, dict(
                    isrc=t.isrc.code,
                    track_metadata=dict(
                        name=t.name,
                        version=t.version,
                        release_date=t.release.release_date.strftime("%Y-%m-%d")
                        if t.release.release_date
                        else None,
                        cover_art=t.release.cover_art.thumbnail_url_400,
                    ),
                )

        if len(q_tracks) != 0:
            # There are items remaining in queue that couldn't be resolved.
            # Yield with default structure.
            for idx in q_tracks:
                yield idx, dict(isrc=t_isrc_map[idx], track_metadata={})

    def enrich_releasedata(self, releases):
        upc_pairs = [
            (idx, r["upc"]) for idx, r in enumerate(releases) if r["upc"] != FAKE_UPC
        ]
        for idx, release_metadata in self.get_enriched_releases(upc_pairs):
            releases[idx]["release_metadata"] = release_metadata

        return releases

    def enrich_tracks(self, tracks):
        isrc_pairs = [(idx, p["isrc"]) for idx, p in enumerate(tracks)]
        for idx, track_metadata in self.get_enriched_tracks(isrc_pairs):
            tracks[idx].update(track_metadata)

        return tracks
