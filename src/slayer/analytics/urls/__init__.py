from django.conf.urls import url, include

from . import artist, release, track

urlpatterns = [
    url(
        r"^artist/",
        include(artist.urlpatterns + release.urlpatterns + track.urlpatterns),
    )
]
