from rest_framework import serializers

from amuse.api.v4.serializers.coverart import CoverArtSerializer
from amuse.api.v4.serializers.song_metadata import SongMetadataSerializer
from releases.models import Release


class ReleaseMetadataSerializer(serializers.ModelSerializer):
    PENDING_APPROVAL_STATUSES = [
        Release.STATUS_SUBMITTED,
        Release.STATUS_PENDING,
        Release.STATUS_APPROVED,
        Release.STATUS_UNDELIVERABLE,
    ]
    NOT_APPROVED_STATUSES = [Release.STATUS_NOT_APPROVED, Release.STATUS_INCOMPLETE]
    MAPPED_PENDING_APPROVAL = 'pending_approval'
    MAPPED_NOT_APPROVED = 'not_approved'
    MAPPED_DELIVERED = 'delivered'
    MAPPED_RELEASED = 'released'
    MAPPED_TAKEDOWN = 'takedown'
    STATUS_UNKNOWN = 'unknown'

    MAPPED_STATUS_BY_ACTUAL_STATUS = {
        Release.STATUS_DELIVERED: MAPPED_DELIVERED,
        Release.STATUS_RELEASED: MAPPED_RELEASED,
        Release.STATUS_TAKEDOWN: MAPPED_TAKEDOWN,
    }

    cover_art = CoverArtSerializer(read_only=True)
    main_primary_artist = serializers.SerializerMethodField()
    songs = SongMetadataSerializer(many=True)
    status = serializers.SerializerMethodField()

    def get_main_primary_artist(self, release):
        artist = release.main_primary_artist
        if artist:
            return artist.name
        return ''

    @staticmethod
    def get_status(release):
        status = release.status
        if status in ReleaseMetadataSerializer.PENDING_APPROVAL_STATUSES:
            mapped_status = ReleaseMetadataSerializer.MAPPED_PENDING_APPROVAL
        elif status in ReleaseMetadataSerializer.NOT_APPROVED_STATUSES:
            mapped_status = ReleaseMetadataSerializer.MAPPED_NOT_APPROVED
        else:
            mapped_status = (
                ReleaseMetadataSerializer.MAPPED_STATUS_BY_ACTUAL_STATUS.get(
                    status, ReleaseMetadataSerializer.STATUS_UNKNOWN
                )
            )
        return mapped_status

    class Meta:
        model = Release
        fields = ('id', 'cover_art', 'main_primary_artist', 'name', 'songs', 'status')
