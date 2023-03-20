from django.db import models

from amuse.models.deliveries import BatchDeliveryRelease
from releases.models import Release, Store
from releases.models.fuga_metadata import FugaStores, FugaDeliveryHistory


class ReleaseStoreDeliveryStatus(models.Model):
    STATUS_DELIVERED = "delivered"
    STATUS_TAKEDOWN = "taken_down"

    release = models.ForeignKey(
        Release, on_delete=models.CASCADE, null=True, blank=True
    )
    store = models.ForeignKey(Store, on_delete=models.CASCADE, null=True, blank=True)
    fuga_store = models.ForeignKey(
        FugaStores, on_delete=models.CASCADE, null=True, blank=True
    )
    status = models.CharField(max_length=128, blank=False, null=False, db_index=True)
    verified = models.BooleanField(
        null=True, default=None, editable=False, db_index=True
    )
    dsp_release_id = models.CharField(
        max_length=1024, blank=False, null=True, db_index=True
    )
    latest_delivery_log = models.ForeignKey(
        BatchDeliveryRelease, on_delete=models.SET_NULL, null=True, blank=True
    )
    latest_fuga_delivery_log = models.ForeignKey(
        FugaDeliveryHistory, on_delete=models.SET_NULL, null=True, blank=True
    )
    updated_at = models.DateTimeField(auto_now=True, editable=False)
    created_at = models.DateTimeField(auto_now_add=True, editable=False)
    delivered_at = models.DateTimeField(null=False)
