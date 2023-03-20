from django.db import models
from . import Song


class AudibleMagicMatch(models.Model):
    type = models.CharField(max_length=128, null=False)

    track = models.CharField(max_length=128, null=False)
    album = models.CharField(max_length=128, null=False)
    artist = models.CharField(max_length=128, null=False)

    upc = models.CharField(max_length=128, null=False)
    isrc = models.CharField(max_length=128, null=False)

    song = models.ForeignKey(Song, on_delete=models.CASCADE)
