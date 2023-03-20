import logging

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from amuse.api.v5.serializers.link import LinkSerializer
from amuse.models.link import Link

logger = logging.getLogger(__name__)


class LinkView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        link_objects = Link.objects.all()
        link_data = LinkSerializer(link_objects, many=True).data
        data = {}
        if link_data:
            for link in link_data:
                name = link.pop('name')
                data[name] = link.pop('link')
        return Response(status=status.HTTP_200_OK, data={'data': data})
