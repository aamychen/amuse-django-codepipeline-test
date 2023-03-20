from django.urls import path
from django.conf.urls import url, include
from django.contrib import admin
from apidocs.urls import urlpatterns as apidocs_urlpatterns


urlpatterns = [
    url(r'^docs/api/', include(apidocs_urlpatterns)),
    path(r'', admin.site.urls),
]
