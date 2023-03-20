from rest_framework.versioning import QueryParameterVersioning
from drf_spectacular.views import (
    SpectacularYAMLAPIView,
    SpectacularRedocView,
    SpectacularSwaggerView,
)


class OpenAPISchemaVersioning(QueryParameterVersioning):
    """Sets a default version to use with query parameter versioning"""

    default_version = 5


class OpenAPIBaseView(SpectacularYAMLAPIView):
    """Overrides versioning with QueryParameterVersioning"""

    versioning_class = OpenAPISchemaVersioning


class OpenAPIRedocView(SpectacularRedocView, OpenAPIBaseView):
    url_name = 'oas-base'


class OpenAPISwaggerView(SpectacularSwaggerView, OpenAPIBaseView):
    url_name = 'oas-base'
