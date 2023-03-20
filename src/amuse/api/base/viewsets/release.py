from django.db.models import Q
from django.views.decorators.cache import cache_control
from rest_framework import mixins, permissions, status, viewsets
from rest_framework.response import Response
from django_filters import rest_framework as filters

from amuse.api.v4.serializers.release import ReleaseSerializer as ReleaseV4Serializer
from amuse.permissions import (
    FrozenUserPermission,
    IsOwnerPermission,
    CanManageReleasesPermission,
    CanDeleteReleasesPermission,
    CanCreateReleasesPermission,
)
from amuse.throttling import IPBlockThrottle
from amuse import mixins as logmixins

from releases.filtersets import ReleaseArtistV2FilterSet
from releases.models import Release, SongArtistRole
from amuse.api.base.views.exceptions import WrongAPIversionError


class ReleaseViewSet(
    logmixins.LogMixin,
    mixins.ListModelMixin,
    mixins.CreateModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    permission_classes = (permissions.IsAuthenticated,)
    queryset = Release.objects.all()
    throttle_classes = (IPBlockThrottle,)
    filter_backends = (filters.DjangoFilterBackend,)
    filterset_class = ReleaseArtistV2FilterSet

    def get_serializer_context(self):
        context = super(ReleaseViewSet, self).get_serializer_context()
        context.update({"request": self.request})
        return context

    def get_permissions(self):
        if self.action == 'destroy':
            self.permission_classes = self.permission_classes + (
                FrozenUserPermission,
                CanDeleteReleasesPermission,
            )
        elif self.action == 'create':
            self.permission_classes = self.permission_classes + (
                FrozenUserPermission,
                CanCreateReleasesPermission,
            )
        elif self.action not in ['list', 'retrieve']:
            self.permission_classes = self.permission_classes + (
                FrozenUserPermission,
                CanManageReleasesPermission,
            )
        return [permission() for permission in self.permission_classes]

    def get_serializer_class(self):
        if self.request.version in ['1', '2', '3']:
            raise WrongAPIversionError()

        return ReleaseV4Serializer

    def get_queryset(self):
        user = self.request.user
        artists = list(user.artists.values_list("id", flat=True))
        songs = list(
            SongArtistRole.objects.filter(artist_id__in=artists).values_list(
                "song_id", flat=True
            )
        )

        r1 = list(Release.objects.filter(songs__in=songs).values_list("id", flat=True))
        r2 = list(Release.objects.filter(user=user).values_list("id", flat=True))

        return (
            self.queryset.filter(id__in=r1 + r2)
            .exclude(status__in=[Release.STATUS_DELETED, Release.STATUS_REJECTED])
            .distinct()
        )

    @cache_control(max_age=7200)
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        success = self.get_object().set_status_deleted()
        if success:
            return Response(status=status.HTTP_204_NO_CONTENT)
        else:
            return Response(status=status.HTTP_403_FORBIDDEN)
