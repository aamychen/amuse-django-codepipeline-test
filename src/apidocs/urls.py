from django.urls import path

from .views import OpenAPIBaseView, OpenAPIRedocView, OpenAPISwaggerView

urlpatterns = [
    path(r'schema/', OpenAPIBaseView.as_view(), name='oas-base'),
    path(r'redoc/', OpenAPIRedocView.as_view(), name='oas-redoc'),
    path(r'swagger/', OpenAPISwaggerView.as_view(), name='oas-swagger'),
]
