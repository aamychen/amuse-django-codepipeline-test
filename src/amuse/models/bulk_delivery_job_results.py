from django.db import models

from amuse.models.bulk_delivery_job import BulkDeliveryJob
from amuse.models.deliveries import Batch
from releases.models import Store


class BulkDeliveryJobResult(models.Model):
    STATUS_UNPROCESSED = 0
    STATUS_FAILED = 1
    STATUS_PREVENTED = 2
    STATUS_SUCCESSFUL = 3

    STATUS_OPTIONS = {
        STATUS_UNPROCESSED: 'unprocessed',
        STATUS_FAILED: 'failed',
        STATUS_PREVENTED: 'prevented',
        STATUS_SUCCESSFUL: 'successful',
    }

    job = models.ForeignKey(BulkDeliveryJob, on_delete=models.CASCADE)
    release = models.ForeignKey('releases.Release', on_delete=models.CASCADE)
    store = models.ForeignKey(
        Store, on_delete=models.CASCADE, null=True, editable=False
    )
    batch = models.ForeignKey(Batch, on_delete=models.SET_NULL, null=True, default=None)

    status = models.PositiveSmallIntegerField(
        default=STATUS_UNPROCESSED,
        choices=[(k, v) for k, v in STATUS_OPTIONS.items()],
        editable=False,
        db_index=True,
    )
    description = models.CharField(max_length=512, null=True, editable=False)

    date_created = models.DateTimeField(auto_now_add=True)
    date_updated = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('job', 'release', 'store')
        verbose_name_plural = 'Bulk Delivery Job Results'
