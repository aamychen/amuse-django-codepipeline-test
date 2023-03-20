from django.db import models
from django.core.validators import MinLengthValidator


class FugaLanguage(models.Manager):
    def get_queryset(self):
        return super().get_queryset().filter(fuga_code__isnull=False)


class MetadataLanguage(models.Model):
    DEFAULT_SORT_ORDER = 999

    name = models.CharField(max_length=120, blank=True)
    fuga_code = models.CharField(
        max_length=25, unique=True, null=True, blank=True, default="en"
    )
    iso_639_1 = models.CharField(
        null=True, blank=True, validators=[MinLengthValidator(2)], max_length=2
    )
    iso_639_2 = models.CharField(
        null=True, blank=True, validators=[MinLengthValidator(3)], max_length=3
    )
    sort_order = models.PositiveSmallIntegerField(default=DEFAULT_SORT_ORDER)

    objects = FugaLanguage()

    is_title_language = models.BooleanField(default=True)
    is_lyrics_language = models.BooleanField(default=True)

    class Meta:
        ordering = ['sort_order', 'name']

    @classmethod
    def by_code(cls, code: str):
        if not code:
            return cls.objects.none()

        langs = cls.objects.filter(fuga_code=code)

        if langs:
            return langs[0]

        return None

    def __str__(self):
        return "%s (%s)" % (self.name, self.fuga_code)
