from rest_framework import permissions, generics

from amuse.api.base.mixins import ArtistAuthorizationMixin
from amuse.api.base.views.exceptions import WrongAPIversionError
from amuse.api.v4.serializers import store as v4
from releases.models import Store


class StoreView(ArtistAuthorizationMixin, generics.ListAPIView):
    serializer_class = v4.StoreSerializer
    permission_classes = [permissions.AllowAny]

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        if self.request.version != '4':
            raise WrongAPIversionError()

    def get_queryset(self):
        qs = (
            Store.objects.select_related('category')
            .exclude(internal_name='audiomack')
            .order_by('order')
        )

        if not self.request.user.is_authenticated:
            return qs

        artist_id = self.request.query_params.get('artist_id', None)

        if not artist_id:
            return qs
        artist = self.get_authorized_artist_with_release_permission(
            artist_id=artist_id, user_id=self.request.user.pk
        )

        if artist and artist.audiomack_id is not None:
            return Store.objects.select_related('category').all().order_by('order')

        return qs
