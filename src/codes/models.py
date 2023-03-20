from django.db import models, transaction

FAKE_UPC = '0000000000000'
FAKE_ISRC = 'NULL00000000'

MANAGED_ISRC_STEMS = [
    'SE5BU',
    'SE575',
    'SE6A9',
    'SE6HN',
    'SE6I3',
    'SE6QE',
    'SE6SA',
    'SE6TI',
    'SE6XW',
    'SE6XX',
    'SE6XY',
    'SE62M',
    'SE66N',
]


class CodeManager(models.Manager):
    def first_unused(self):
        return (
            self.get_queryset()
            .select_for_update()
            .filter(status=Code.STATUS_UNUSED)[:1][0]
        )

    def use(self, code):
        """
        Gets or creates a new code, or picks the first unused if code is None
        :param code: str|None: A code to use or None
        :return: Code
        """
        if code:
            return self.get_queryset().get_or_create(
                code=code, status=Code.STATUS_USED
            )[0]
        with transaction.atomic():
            code = self.first_unused()
            code.status = Code.STATUS_USED
            code.save()
            return code


class Code(models.Model):
    STATUS_UNUSED = 0
    STATUS_USED = 1
    STATUS_ORPHANED = 2

    STATUS_CHOICES = (
        (STATUS_UNUSED, 'Unused'),
        (STATUS_USED, 'Used'),
        (STATUS_ORPHANED, 'Orphaned'),
    )

    code = models.CharField(max_length=32, null=False, blank=False, unique=True)
    status = models.SmallIntegerField(default=STATUS_UNUSED, choices=STATUS_CHOICES)

    objects = CodeManager()

    def __str__(self):
        return self.code

    class Meta:
        abstract = True


class ISRC(Code):
    class Meta:
        verbose_name = verbose_name_plural = 'ISRC'

    licensed = models.BooleanField(
        default=False, help_text='Denotes whether this ISRC has been licened by Amuse.'
    )


class UPC(Code):
    class Meta:
        verbose_name = verbose_name_plural = 'UPC'
