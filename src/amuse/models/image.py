from django.db import models


class Image(models.Model):
    date_created = models.DateTimeField(auto_now_add=True)
    path = models.TextField()
    mime = models.TextField(null=True)
    size = models.IntegerField(null=True)
    width = models.IntegerField(null=True)
    height = models.IntegerField(null=True)
