from rest_framework import status
from rest_framework.decorators import permission_classes
from rest_framework.generics import GenericAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from amuse.api.base.views.exceptions import WrongAPIversionError
from amuse.api.v5.serializers.user_metadata import UserMetadataSerializer
from users.models import UserMetadata
from amuse.analytics import sign_up

from amuse.platform import PlatformHelper


@permission_classes([IsAuthenticated])
class UserMetadataView(GenericAPIView):
    def get_serializer_class(self):
        if not self.request.version == '5':
            raise WrongAPIversionError()

        return UserMetadataSerializer

    def put(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user_metadata, _ = UserMetadata.objects.get_or_create(user=self.request.user)
        user_metadata.impact_click_id = serializer.validated_data.get('impact_click_id')
        user_metadata.save()

        platform = PlatformHelper.from_request(request)
        sign_up(request.user, platform, user_metadata.impact_click_id)

        return Response({'is_success': True}, status=status.HTTP_200_OK)
