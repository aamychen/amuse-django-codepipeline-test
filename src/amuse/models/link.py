from django.db import models


class Link(models.Model):
    name = models.CharField(max_length=120, unique=True, null=False)
    link = models.URLField(max_length=1000, blank=False, null=False)
    updated_at = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)
