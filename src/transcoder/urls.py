from django.conf.urls import url
from transcoder.views import callback

urlpatterns = [url(r'callback/', callback)]
