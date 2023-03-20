from amuse import mixins as logmixins
from rest_framework import mixins, permissions, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from django.db.models import Case, When, Value, IntegerField

from amuse.api.v4.serializers.artist import ArtistSerializer as ArtistV4Serializer
from amuse.api.v4.serializers.artist_team import ArtistTeamSerializer
from amuse.api.v4.serializers.artist import ArtistSoMeUpdateSerializer
from users.models import ArtistV2, UserArtistRole
from amuse.permissions import (
    FrozenUserPermission,
    CanManageArtistPermission,
    CanManageArtistSoMeDataPermission,
)


class ArtistViewSet(
    logmixins.LogMixin,
    mixins.ListModelMixin,
    mixins.CreateModelMixin,
    mixins.UpdateModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    permission_classes = (permissions.IsAuthenticated,)
    queryset = ArtistV2.objects.all()
    serializer_class = ArtistV4Serializer

    def get_permissions(self):
        if self.action == 'create':
            self.permission_classes = self.permission_classes + (FrozenUserPermission,)

        if self.action in ['list', 'create', 'update', 'retrieve']:
            self.permission_classes = self.permission_classes + (
                CanManageArtistPermission,
            )
        return [permission() for permission in self.permission_classes]

    def get_queryset(self):
        return (
            ArtistV2.objects.filter(userartistrole__user=self.request.user)
            .annotate(
                order=Case(
                    When(userartistrole__type=UserArtistRole.OWNER, then=Value(1)),
                    When(userartistrole__type=UserArtistRole.ADMIN, then=Value(2)),
                    When(userartistrole__type=UserArtistRole.MEMBER, then=Value(3)),
                    When(userartistrole__type=UserArtistRole.SPECTATOR, then=Value(4)),
                    default=Value(5),
                    output_field=IntegerField(),
                )
            )
            .order_by('order')
            .all()
            .select_related('owner')
        )

    @action(
        detail=True,
        methods=['get'],
        permission_classes=(permissions.IsAuthenticated, CanManageArtistPermission),
    )
    def team(self, request, pk):
        serializer = ArtistTeamSerializer(
            self.get_object(), context={'user': request.user, 'artist_id': pk}
        )
        return Response(serializer.data)

    @action(
        detail=True,
        methods=['post'],
        permission_classes=(
            permissions.IsAuthenticated,
            CanManageArtistSoMeDataPermission,
        ),
    )
    def social_media(self, request, pk):
        some_update_serializer = ArtistSoMeUpdateSerializer(
            self.get_object(), data=request.data, context=self.get_serializer_context()
        )
        some_update_serializer.is_valid(raise_exception=True)
        some_update_serializer.save()

        artist_serializer = ArtistV4Serializer(
            some_update_serializer.instance, context=self.get_serializer_context()
        )
        return Response(artist_serializer.data)
