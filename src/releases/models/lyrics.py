from django.db import models
from releases.models.song import Song


class LyricsAnalysisResult(models.Model):
    explicit = models.BooleanField()
    text = models.TextField()
    date_created = models.DateTimeField(auto_now_add=True)
    date_updated = models.DateTimeField(auto_now=True)
    song = models.OneToOneField(Song, on_delete=models.CASCADE)
