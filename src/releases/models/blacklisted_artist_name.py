from django.db import models

from amuse.vendor.spotify.artist_blacklist.blacklist import fuzzify


class BlacklistedArtistName(models.Model):
    name = models.CharField(max_length=255, unique=True)
    fuzzy_name = models.CharField(max_length=255)
    is_active = models.BooleanField(default=True)
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        self.fuzzy_name = fuzzify(self.name)
        super().save(*args, **kwargs)
