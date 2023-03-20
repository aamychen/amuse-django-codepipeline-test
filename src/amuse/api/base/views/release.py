from rest_framework.generics import ListAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from amuse.api.v4.serializers.release_metadata import ReleaseMetadataSerializer
from amuse.mixins import LogMixin
from releases.models import Release, RoyaltySplit


class ReleaseMetadataView(LogMixin, ListAPIView):
    serializer_class = ReleaseMetadataSerializer
    permission_classes = [IsAuthenticated]

    def list(self, request, *args, **kwargs):
        release_ids = (
            request.user.royaltysplit_set.filter(
                status__in=(RoyaltySplit.STATUS_ACTIVE, RoyaltySplit.STATUS_ARCHIVED)
            )
            .values_list('song__release_id', flat=True)
            .distinct()
        )
        releases = Release.objects.filter(pk__in=release_ids)

        serializer = self.get_serializer(releases, many=True)
        return Response(serializer.data)
