from django.db import models
from django.contrib.postgres import fields as pgfields
from app.store import APPLE, STORE_OPTIONS
from releases.models import Release


class Delivery(models.Model):
    STATUS_SUBMITTED = 0
    STATUS_SUCCEEDED = 1
    STATUS_FAILED = 99

    STATUS_OPTIONS = {
        STATUS_SUBMITTED: 'SUBMITTED',
        STATUS_SUCCEEDED: 'SUCCEEDED',
        STATUS_FAILED: 'FAILED',
    }

    batch_job = models.CharField(max_length=120, unique=True, null=True)

    store = models.PositiveSmallIntegerField(
        choices=((APPLE, STORE_OPTIONS[APPLE]),), db_index=True
    )

    status = models.PositiveSmallIntegerField(
        default=STATUS_SUBMITTED,
        choices=(
            (STATUS_SUBMITTED, STATUS_OPTIONS[STATUS_SUBMITTED]),
            (STATUS_SUCCEEDED, STATUS_OPTIONS[STATUS_SUCCEEDED]),
            (STATUS_FAILED, STATUS_OPTIONS[STATUS_FAILED]),
        ),
        db_index=True,
    )

    errors = pgfields.ArrayField(models.CharField(max_length=512), default=list)
    warnings = pgfields.ArrayField(models.CharField(max_length=512), default=list)

    date_created = models.DateTimeField(auto_now_add=True)
    date_updated = models.DateTimeField(auto_now=True)

    release = models.ForeignKey(Release, on_delete=models.CASCADE)

    @classmethod
    def internal_status(cls, external_status):
        return list(cls.STATUS_OPTIONS.keys())[
            list(cls.STATUS_OPTIONS.values()).index(external_status)
        ]

    @classmethod
    def external_status(cls, internal_status):
        return cls.STATUS_OPTIONS[internal_status]

    class Meta:
        db_table = 'delivery'
        verbose_name_plural = 'Deliveries'
