from django.db import models
from releases.models.song import Song
from django.db.models import JSONField


class ACRCloudMatch(models.Model):
    score = models.PositiveSmallIntegerField()
    offset = models.PositiveSmallIntegerField()

    artist_name = models.CharField(max_length=255)
    album_title = models.CharField(max_length=255)
    track_title = models.CharField(max_length=255)

    match_upc = models.CharField(max_length=32, null=True)
    match_isrc = models.CharField(max_length=32, null=True)

    external_metadata = JSONField(null=True)

    song = models.ForeignKey(
        Song, on_delete=models.CASCADE, related_name='acrcloud_matches'
    )

    class Meta:
        db_table = 'acrcloud_match'
        verbose_name = 'ACRCloud match'
        verbose_name_plural = 'ACRCloud matches'
