from .analytics.urls import urlpatterns as analytics_urlpatterns

from django.conf.urls import url, include


urlpatterns = [url(r'^analytics/', include(analytics_urlpatterns))]
