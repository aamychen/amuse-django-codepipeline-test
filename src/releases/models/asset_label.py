import re
from django.db import models
from django.core.exceptions import ValidationError
from releases.models import Release, Song


def validate_asset_label(label):
    if re.match(r"^[a-zA-Z0-9\-\_]{2,50}$", label) is None:
        raise ValidationError(
            "asset label can not contain spaces or special characters"
            "and must be 2-50 characters long"
        )


class AssetLabel(models.Model):
    name = models.TextField(
        max_length=50,
        blank=False,
        null=False,
        unique=True,
        validators=[validate_asset_label],
    )
    releases = models.ManyToManyField(Release, through='ReleaseAssetLabel')
    songs = models.ManyToManyField(Song, through='SongAssetLabel')

    def save(self, *args, **kwargs):
        self.name = self.name.lower()
        return super(AssetLabel, self).save(*args, **kwargs)

    def __str__(self):
        return self.name


class ReleaseAssetLabel(models.Model):
    release = models.ForeignKey(
        Release, related_name='asset_labels', on_delete=models.CASCADE
    )
    asset_label = models.ForeignKey(AssetLabel, on_delete=models.DO_NOTHING)

    class Meta:
        unique_together = ("release", "asset_label")

    def __str__(self):
        return f"<{self.asset_label.name}> <{self.release.name}>"


class SongAssetLabel(models.Model):
    song = models.ForeignKey(
        Song, related_name='asset_labels', on_delete=models.CASCADE
    )
    asset_label = models.ForeignKey(AssetLabel, on_delete=models.DO_NOTHING)

    class Meta:
        unique_together = ("song", "asset_label")

    def __str__(self):
        return f"<{self.asset_label.name}> <{self.song.name}>"
