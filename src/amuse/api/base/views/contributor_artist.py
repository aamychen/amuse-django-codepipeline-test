from rest_framework import generics
from rest_framework.decorators import permission_classes
from rest_framework.permissions import IsAuthenticated

from amuse.api.v4.serializers.artist import ContibutorArtistSerializer
from amuse.api.base.views.exceptions import WrongAPIversionError
from amuse import mixins as logmixins


@permission_classes([IsAuthenticated])
class ContibutorArtistView(logmixins.LogMixin, generics.CreateAPIView):
    serializer_class = ContibutorArtistSerializer

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        if not self.request.version == '4':
            raise WrongAPIversionError()
