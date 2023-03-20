from datetime import datetime

from amuse.deliveries import CHANNELS
from amuse.storages import S3Storage
from django.conf import settings
from django.contrib.postgres import fields as pgfields
from django.db import models
from users.models.user import User


def _batch_delivery_id():
    return datetime.utcnow().strftime('%Y%m%d%H%M%S%f')[:-3]


class Batch(models.Model):
    STATUS_CREATED = 0
    STATUS_SUCCEEDED = 1
    STATUS_STARTED = 98
    STATUS_FAILED = 99

    STATUS_OPTIONS = {
        STATUS_CREATED: 'created',
        STATUS_SUCCEEDED: 'succeeded',
        STATUS_STARTED: 'started',
        STATUS_FAILED: 'failed',
    }

    file = models.FileField(
        storage=S3Storage(bucket_name=settings.AWS_BATCH_DELIVERY_FILE_BUCKET_NAME)
    )
    status = models.PositiveSmallIntegerField(
        default=STATUS_CREATED,
        choices=[(k, v) for k, v in STATUS_OPTIONS.items()],
        db_index=True,
    )
    date_created = models.DateTimeField(auto_now_add=True)
    date_updated = models.DateTimeField(auto_now=True)

    user = models.ForeignKey(User, on_delete=models.SET_NULL, blank=True, null=True)

    class Meta:
        verbose_name_plural = 'Batches'


class BatchDelivery(models.Model):
    STATUS_CREATED = 0
    STATUS_SUCCEEDED = 1
    STATUS_STARTED = 10
    STATUS_AMBIGUOUS = 50
    STATUS_FAILED = 99

    STATUS_OPTIONS = {
        STATUS_CREATED: 'created',
        STATUS_SUCCEEDED: 'succeeded',
        STATUS_STARTED: 'started',
        STATUS_AMBIGUOUS: 'ambiguous',
        STATUS_FAILED: 'failed',
    }

    delivery_id = models.CharField(
        max_length=18, default=_batch_delivery_id, db_index=True
    )
    channel = models.PositiveSmallIntegerField(
        choices=[(k, v.lower()) for k, v in CHANNELS.items()], db_index=True
    )
    status = models.PositiveSmallIntegerField(
        default=STATUS_CREATED,
        choices=[(k, v) for k, v in STATUS_OPTIONS.items()],
        db_index=True,
    )
    date_created = models.DateTimeField(auto_now_add=True)
    date_updated = models.DateTimeField(auto_now=True)

    batch = models.ForeignKey(Batch, on_delete=models.CASCADE, blank=True, null=True)

    releases = models.ManyToManyField(
        'releases.Release', through='BatchDeliveryRelease'
    )

    def __str__(self):
        return str(self.pk)

    class Meta:
        db_table = 'batch_delivery'
        verbose_name_plural = 'Batch Deliveries'


class BatchDeliveryRelease(models.Model):
    STATUS_CREATED = 0
    STATUS_STARTED = 1
    STATUS_SUCCEEDED = 2
    STATUS_INTERIM_STORAGE = 10
    STATUS_REDELIVERED = 11
    STATUS_FAILED = 99

    STATUS_OPTIONS = {
        STATUS_CREATED: 'created',
        STATUS_STARTED: 'started',
        STATUS_SUCCEEDED: 'succeeded',
        STATUS_INTERIM_STORAGE: 'storing',
        STATUS_REDELIVERED: 'redelivered',
        STATUS_FAILED: 'failed',
    }

    DELIVERY_TYPE_INSERT = 0
    DELIVERY_TYPE_UPDATE = 1
    DELIVERY_TYPE_TAKEDOWN = 2
    DELIVERY_TYPE_PRO_TAKEDOWN = 3

    DELIVERY_TYPE_OPTIONS = {
        DELIVERY_TYPE_INSERT: 'insert',
        DELIVERY_TYPE_UPDATE: 'update',
        DELIVERY_TYPE_TAKEDOWN: 'takedown',
        DELIVERY_TYPE_PRO_TAKEDOWN: 'pro_takedown',
    }

    status = models.PositiveSmallIntegerField(
        default=STATUS_CREATED,
        choices=[(k, v) for k, v in STATUS_OPTIONS.items()],
        db_index=True,
    )
    type = models.PositiveSmallIntegerField(
        default=DELIVERY_TYPE_INSERT,
        choices=[(k, v) for k, v in DELIVERY_TYPE_OPTIONS.items()],
        db_index=True,
    )
    errors = pgfields.ArrayField(models.CharField(max_length=2048), default=list)
    warnings = pgfields.ArrayField(models.CharField(max_length=2048), default=list)
    delivery = models.ForeignKey(BatchDelivery, on_delete=models.CASCADE)
    release = models.ForeignKey('releases.Release', on_delete=models.CASCADE)

    excluded_stores = models.ManyToManyField(
        'releases.Store',
        blank=True,
        help_text='This is the stores to <strong>exclude</strong> from delivery.',
    )
    stores = models.ManyToManyField(
        'releases.Store',
        blank=True,
        help_text='This is a static snapshot of the stores delivered to.',
        related_name='delivery_stores',
    )
    redeliver = models.BooleanField(
        blank=True, default=False, null=True, help_text='Mark this for re-delivery.'
    )
    redeliveries = models.ManyToManyField(
        'self', blank=True, symmetrical=False, help_text='Redeliveries of this delivery'
    )

    def __str__(self):
        return f'{self.release.name} ({self.release.id})'

    class Meta:
        db_table = 'batch_delivery_release'
