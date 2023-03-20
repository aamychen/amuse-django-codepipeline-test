from abc import ABC, abstractmethod

from rest_framework.decorators import permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.generics import GenericAPIView
from rest_framework.response import Response
from rest_framework import status, serializers as drf_serializers
from drf_spectacular.views import extend_schema
from drf_spectacular.utils import extend_schema_serializer
from django.views.decorators.cache import cache_control
from waffle import switch_is_active

from amuse.api.base.views.exceptions import WrongAPIversionError
from amuse.mixins import LogMixin
from amuse.logging import logger


# @TODO: Move response related stuff into nested response class
@permission_classes([IsAuthenticated])
class AnalyticsBaseView(LogMixin, GenericAPIView):
    def __init__(self, *args, **kwargs):
        extend_schema(
            description=self.serializer_docstring,
            responses={200: self.success_envelope, 500: self.error_envelope},
        )(self.__class__)
        super(AnalyticsBaseView, self).__init__(*args, **kwargs)

    @property
    @abstractmethod
    def slayer_fn(self):
        pass

    @property
    def serializer_docstring(self):
        doc = self.serializer_class.Request.Meta.dataclass.__doc__
        return doc.strip()

    @property
    def error_envelope(self):
        name = f"Error{self.serializer_class.__name__}"

        @extend_schema_serializer(component_name=name)
        class ErrorEnvelope(drf_serializers.Serializer):
            data = drf_serializers.CharField(required=False, help_text="Not used")
            is_success = drf_serializers.BooleanField(
                default=False, help_text="Is set to `false` for unsuccessful requests"
            )
            reason = drf_serializers.CharField(
                required=False, help_text="HTTP Status text"
            )

        return ErrorEnvelope

    @property
    def success_envelope(self):
        name = f"Success{self.serializer_class.__name__}"

        @extend_schema_serializer(component_name=name)
        class SuccessEnvelope(drf_serializers.Serializer):
            data = self.serializer_class(
                required=False, help_text="JSON-serialized Response Data"
            )
            is_success = drf_serializers.BooleanField(
                default=True, help_text="Is set to `true` for successful requests"
            )
            reason = drf_serializers.CharField(required=False, help_text="Not used")

        return SuccessEnvelope

    @property
    def slayer_args(self):
        if not hasattr(self, "kwargs"):
            return

        kwargs = self.kwargs.copy()
        if self.resp_limit:
            kwargs["response_length"] = self.resp_limit

        serializer = self.serializer_class.Request(data=kwargs)
        if serializer.is_valid():
            return serializer.data
        else:
            logger.warning(f"Slayer request validation failed: {serializer.errors}")
            raise self.resp_500()

    def slayer_invoke(self, **kwargs_override):
        kwargs = self.slayer_args.copy()
        kwargs.update(kwargs_override)
        return self.slayer_fn(**kwargs)

    @property
    def resp_limit(self):
        return int(self.request.query_params.get('limit', 0))

    def resp_200(self, data):
        serializer = self.success_envelope(
            data=dict(is_success=True, reason=None, data=data)
        )
        return Response(serializer.initial_data, status=status.HTTP_200_OK)

    def resp_err(self, http_status, text="Server error"):
        serializer = self.error_envelope(
            data=dict(is_success=False, reason=text, data=None)
        )
        return Response(serializer.initial_data, status=http_status)

    @cache_control(max_age=7200)
    def get(self, request, **kwargs):
        if not request.version == "5":
            raise WrongAPIversionError()

        if not switch_is_active("streaminganalytics:enabled"):
            self.resp_err(status.HTTP_503_SERVICE_UNAVAILABLE, "Disabled")

        try:
            response = self.slayer_invoke()
        except Exception as e:
            # Something went wrong when communicating with Slayer
            # Log the exception and return HTTP 500.
            logger.exception(e)
            return self.resp_err(status.HTTP_500_INTERNAL_SERVER_ERROR)

        serializer = self.serializer_class(data=response)
        serializer.enrich(context=self.slayer_args)

        # @TODO: Implement following when metaclasses for populating enrichment
        #        schemas are in place
        # if not serializer.is_valid():
        #    logger.warning(f"Unexpected response: {serializer.errors}")
        #    return self.resp_err(status.HTTP_500_INTERNAL_SERVER_ERROR)

        return self.resp_200(serializer.initial_data)


@extend_schema(tags=["Artist"])
class AnalyticsArtistView(AnalyticsBaseView, ABC):
    pass


@extend_schema(tags=["Release"])
class AnalyticsReleaseView(AnalyticsBaseView, ABC):
    pass


@extend_schema(tags=["Track"])
class AnalyticsTrackView(AnalyticsBaseView, ABC):
    pass
