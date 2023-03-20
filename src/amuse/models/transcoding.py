from django.db import models
from django.contrib.postgres import fields as pgfields


class Transcoding(models.Model):
    STATUS_SUBMITTED = 0
    STATUS_COMPLETED = 1
    STATUS_PROGRESSING = 2
    STATUS_WARNING = 3
    STATUS_ERROR = 4

    STATUS_OPTIONS = {
        STATUS_SUBMITTED: 'SUBMITTED',
        STATUS_COMPLETED: 'COMPLETED',
        STATUS_PROGRESSING: 'PROGRESSING',
        STATUS_WARNING: 'WARNING',
        STATUS_ERROR: 'ERROR',
    }

    ELASTIC_TRANSCODER = 1
    AUDIO_TRANSCODER_SERVICE = 2

    TRANSCODER_CHOICES = (
        (ELASTIC_TRANSCODER, 'elastictranscoder'),
        (AUDIO_TRANSCODER_SERVICE, 'audio-transcoder-service'),
    )

    transcoder_job = models.CharField(max_length=120, unique=True, null=True)
    transcoder_name = models.PositiveIntegerField(
        choices=TRANSCODER_CHOICES, default=ELASTIC_TRANSCODER
    )

    status = models.PositiveSmallIntegerField(
        default=STATUS_SUBMITTED,
        choices=(
            (STATUS_SUBMITTED, STATUS_OPTIONS[STATUS_SUBMITTED]),
            (STATUS_COMPLETED, STATUS_OPTIONS[STATUS_COMPLETED]),
            (STATUS_PROGRESSING, STATUS_OPTIONS[STATUS_PROGRESSING]),
            (STATUS_WARNING, STATUS_OPTIONS[STATUS_WARNING]),
            (STATUS_ERROR, STATUS_OPTIONS[STATUS_ERROR]),
        ),
        db_index=True,
    )

    errors = pgfields.ArrayField(models.CharField(max_length=512), default=list)
    warnings = pgfields.ArrayField(models.CharField(max_length=512), default=list)

    date_created = models.DateTimeField(auto_now_add=True)
    date_updated = models.DateTimeField(auto_now=True)

    song = models.ForeignKey('releases.Song', on_delete=models.CASCADE)

    @classmethod
    def internal_status(cls, external_status):
        return list(cls.STATUS_OPTIONS.keys())[
            list(cls.STATUS_OPTIONS.values()).index(external_status)
        ]

    @classmethod
    def external_status(cls, internal_status):
        return cls.STATUS_OPTIONS[internal_status]

    class Meta:
        db_table = 'transcoding'
