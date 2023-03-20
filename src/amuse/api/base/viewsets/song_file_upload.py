from amuse.api.v1.serializers import (
    SongFileUploadSerializer,
    LinkSongFileDownloadSerializer,
    GoogleDriveSongFileDownloadSerializer,
)
from amuse.permissions import IsOwnerPermission
from amuse import mixins as logmixins
from releases.models import SongFileUpload
from rest_framework import mixins, permissions, viewsets


class SongFileUploadViewSet(
    logmixins.LogMixin,
    mixins.CreateModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet,
):
    permission_classes = (permissions.IsAuthenticated, IsOwnerPermission)
    queryset = SongFileUpload.objects.all()
    serializer_class = SongFileUploadSerializer


class GoogleDriveSongFileDownloadViewSet(logmixins.LogMixin, viewsets.ModelViewSet):
    serializer_class = GoogleDriveSongFileDownloadSerializer


class LinkSongFileDownloadViewSet(logmixins.LogMixin, viewsets.ModelViewSet):
    serializer_class = LinkSongFileDownloadSerializer
