import logging

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.exceptions import NotFound
from rest_framework.views import APIView

from amuse import mixins as logmixins
from amuse.api.base.mixins import ArtistAuthorizationMixin

from amuse.api.base.views.exceptions import WrongAPIversionError
from amuse.api.v5.serializers.takedown import TakedownSerializer
from amuse.services.takedown import Takedown, TakedownResponse
from releases.models import Release

logger = logging.getLogger(__name__)

DISPLAY_CODE_ERROR_SPLITS = "takedown_error_splits"
DISPLAY_CODE_ERROR_TAKEDOWN_IN_PROGRESS = "takedown_error_in_progress"
DISPLAY_CODE_ERROR_GENERIC = "takedown_error_generic"
DISPLAY_CODE_ERROR_LICENSED_TRACKS = "takedown_error_licensed_tracks"

ERROR_RESPONSE_MAPPING = {
    TakedownResponse.FAILED_REASON_NOT_LIVE: {
        "display_code": DISPLAY_CODE_ERROR_GENERIC,
        "error_message": "Cannot take down a release that is not live.",
        "form_url": None,
    },
    TakedownResponse.FAILED_REASON_TAKEDOWN_IN_PROGRESS: {
        "display_code": DISPLAY_CODE_ERROR_TAKEDOWN_IN_PROGRESS,
        "error_message": "Cannot take down a release that is in the process of being taken down.",
        "form_url": None,
    },
    TakedownResponse.FAILED_REASON_LOCKED_SPLITS: {
        "display_code": DISPLAY_CODE_ERROR_SPLITS,
        "error_message": "Cannot take down a release that is part of a FFWD deal.",
        "form_url": None,
    },
    TakedownResponse.FAILED_REASON_LICENSED_TRACKS: {
        "display_code": DISPLAY_CODE_ERROR_LICENSED_TRACKS,
        "error_message": "Releases containing tracks that are currently licensed cannot be taken down. ",
        "form_url": None,
    },
}


class TakedownView(ArtistAuthorizationMixin, logmixins.LogMixin, APIView):
    permission_classes = [IsAuthenticated]
    allowed_methods = ["POST"]

    def post(self, request, *args, **kwargs):
        if request.version != '5':
            raise WrongAPIversionError()

        try:
            release = Release.objects.get(pk=kwargs['release_id'])
        except Release.DoesNotExist:
            raise NotFound()

        serializer = TakedownSerializer(
            data=request.data, context={'release': release, 'user': request.user}
        )
        serializer.is_valid(raise_exception=True)

        takedown_response = Takedown(
            release, request.user, serializer.validated_data['takedown_reason']
        ).trigger()

        if takedown_response.success:
            return Response(status=status.HTTP_204_NO_CONTENT)

        if takedown_response.failure_reason in ERROR_RESPONSE_MAPPING:
            return Response(
                status=status.HTTP_405_METHOD_NOT_ALLOWED,
                data=ERROR_RESPONSE_MAPPING[takedown_response.failure_reason],
            )

        logger.error(
            f"Failed to take down release ({release.id}) for unknown reason, triggered by user {request.user.pk}"
        )
        return Response(status=status.HTTP_500_INTERNAL_SERVER_ERROR)
