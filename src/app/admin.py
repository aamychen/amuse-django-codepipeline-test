from django.contrib import admin
from app.models.deliveries import Delivery


@admin.register(Delivery)
class DeliveryAdmin(admin.ModelAdmin):
    list_filter = ('store', 'status')
    list_display = (
        'batch_job',
        'upc_code',
        'release',
        'status_external',
        'date_created',
        'date_updated',
    )

    readonly_fields = ('batch_job', 'store', 'errors', 'warnings', 'release')

    def upc_code(self, obj):
        return obj.release.upc_code

    def status_external(self, obj):
        return Delivery.external_status(obj.status)
