from django.db import models


class Genre(models.Model):
    NO_YT_CONTENT_GENRES = ['Electronic', 'Hip Hop/Rap', 'New Age', 'Latin', 'Dance']

    STATUS_ACTIVE = 1
    STATUS_INACTIVE = 2

    STATUS_CHOICES = ((STATUS_ACTIVE, 'active'), (STATUS_INACTIVE, 'inactive'))

    name = models.CharField(max_length=120, null=False, blank=False, unique=True)
    status = models.SmallIntegerField(default=STATUS_ACTIVE, choices=STATUS_CHOICES)
    parent = models.ForeignKey(
        'Genre',
        null=True,
        blank=True,
        related_name='subgenres',
        on_delete=models.CASCADE,
    )
    apple_code = models.CharField(max_length=120, null=True, blank=True)

    def __str__(self):
        return self.name

    def get_active_subgenres(self):
        return self.subgenres.filter(status=Genre.STATUS_ACTIVE)

    class Meta:
        ordering = ('name',)

    def is_genre_qualified_for_youtube_content_id(self):
        if self.name in self.NO_YT_CONTENT_GENRES:
            return False
        if self.parent and self.parent.name in self.NO_YT_CONTENT_GENRES:
            return False
        return True
