import io
import urllib
from collections import Counter
from datetime import datetime, timedelta
from uuid import uuid4

import pytz
from django import forms
from django.conf import settings
from django.contrib import admin, messages
from django.contrib.admin import SimpleListFilter, DateFieldListFilter
from django.core.files import File
from django.db.models import Count
from django.db.models import Q
from django.http import HttpResponseRedirect
from django.shortcuts import render
from django.urls import reverse, path
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from import_export import resources
from import_export.admin import ExportMixin
from import_export.formats import base_formats

from amuse.csv_splitter import CsvSplitter
from amuse.deliveries import CHANNELS, FUGA
from amuse.models import Transcoding
from amuse.models.acrcloud import ACRCloudMatch
from amuse.models.bulk_delivery_job import BulkDeliveryJob
from amuse.models.bulk_delivery_job_results import BulkDeliveryJobResult
from amuse.models.deliveries import Batch, BatchDelivery, BatchDeliveryRelease
from amuse.models.event import Event
from amuse.models.link import Link
from amuse.models.minfraud_result import MinfraudResult
from amuse.models.utils import NotificationTemplate
from amuse.services.delivery.checks import ALL_DELIVERY_CHECKS
from amuse.tasks import _calculate_django_file_checksum, bulk_delivery_job_command
from amuse.vendor.aws.s3 import create_presigned_url
from releases.models import Release, Song
from releases.models.fuga_metadata import (
    FugaMetadata,
    FugaStores,
    FugaDeliveryHistory,
    FugaPerson,
    FugaArtist,
    FugaProductArtist,
    FugaProductAssetArtist,
    FugaAsset,
    FugaMismatch,
    FugaProductAsset,
    FugaGenre,
    FugaMigrationWave,
    MigrationStatus,
)
from releases.utils import ordered_stores_queryset


@admin.register(ACRCloudMatch)
class ACRCloudMatchAdmin(admin.ModelAdmin):
    list_display = (
        'song',
        'offset',
        'score',
        'artist_name',
        'album_title',
        'track_title',
        'local_upc',
        'match_upc',
        'local_isrc',
        'match_isrc',
        'tollgate_link',
    )
    readonly_fields = (
        'score',
        'offset',
        'artist_name',
        'album_title',
        'track_title',
        'match_upc',
        'match_isrc',
        'external_metadata',
        'song',
    )
    search_fields = ('=song__release__id',)

    def local_upc(self, obj):
        return obj.song.release.upc_code

    local_upc.short_description = 'Amuse UPC'
    local_upc.admin_order_field = 'song__release__upc'

    def local_isrc(self, obj):
        return obj.song.isrc_code

    local_isrc.short_description = 'Amuse ISRC'
    local_isrc.admin_order_field = 'song__isrc_code'

    def tollgate_link(self, obj):
        url = reverse(
            'admin:contenttollgate_genericrelease_view', args=[obj.song.release.id]
        )
        return mark_safe(f'<a href="{url}" target="_blank">See Release</a>')

    tollgate_link.short_description = 'Tollgate Link'

    def has_add_permission(self, request):
        return False


class BatchDeliveryReleaseAdminInline(admin.StackedInline):
    model = BatchDeliveryRelease
    readonly_fields = (
        'type',
        'status',
        'errors',
        'warnings',
        'stores',
        'release_upc',
        'get_xml_url',
        'is_redelivery_for',
        'redeliveries',
    )
    exclude = ('release',)
    raw_id_fields = ('redeliveries',)
    extra = 0
    raw_id_fields = ('redeliveries',)

    def has_add_permission(self, request, obj):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def release_upc(self, instance):
        return instance.release.upc.code

    def is_redelivery_for(self, obj):
        return list(obj.batchdeliveryrelease_set.values_list('id', flat=True))

    def get_xml_url(self, instance):
        if CHANNELS[instance.delivery.channel] == "apple":
            file_path = "%s/%s.itmsp/metadata.xml" % (
                instance.delivery.delivery_id,
                instance.release.upc.code,
            )
        else:
            file_path = "%s/%s/%s.xml" % (
                instance.delivery.delivery_id,
                instance.release.upc.code,
                instance.release.upc.code,
            )

        if settings.AWS_S3_HOST == "s3-dev.amuse.io":
            base_url = "http://%s:%s/minio/%s" % (
                settings.AWS_S3_HOST,
                settings.AWS_S3_PORT,
                settings.AWS_STORAGE_BUCKET_NAME,
            )
            xml_url = '%s/%s' % (base_url, file_path)
        else:
            if instance.delivery.batch is None:
                base_url = "https://%s.%s/batch-delivery" % (
                    settings.AWS_STORAGE_BUCKET_NAME,
                    settings.AWS_S3_HOST,
                )
                xml_url = '%s/%s' % (base_url, file_path)
            else:
                base_url = "https://%s.%s" % (
                    settings.AWS_BATCH_DELIVERY_BUCKET_NAME,
                    settings.AWS_S3_HOST,
                )
                xml_url = create_presigned_url(
                    bucket_name=settings.AWS_BATCH_DELIVERY_BUCKET_NAME,
                    object_name=file_path,
                )

        return format_html('<a href="%s" target="_blank">View XML file</a>' % xml_url)

    get_xml_url.short_description = "Generated XML"


class BatchBoolFilter(SimpleListFilter):
    title = 'Delivery System'
    parameter_name = 'delivery_system'
    filter_string = 'batch__isnull'

    def lookups(self, request, model_admin):
        return [('old', 'Old Delivery System'), ('new', 'New Delivery System')]

    def queryset(self, request, queryset):
        if self.value() == 'new':
            filter_kwargs = {self.filter_string: False}
        elif self.value() == 'old':
            filter_kwargs = {self.filter_string: True}
        else:
            return queryset
        return queryset.filter(**filter_kwargs)


class ReleaseBatchBoolFilter(BatchBoolFilter):
    filter_string = 'delivery__batch__isnull'


class RedeliveryFilter(SimpleListFilter):
    title = 'Redeliveries'
    parameter_name = 'redeliveries'

    def lookups(self, request, model_admin):
        return [
            ('is_redelivery', 'Is a redelivery'),
            ('has_redelivery', 'Has been redelivered'),
            ('has_no_redelivery', 'Has not been redelivered'),
        ]

    def queryset(self, request, queryset):
        if self.value() == 'is_redelivery':
            filter_kwargs = {'batchdeliveryrelease__isnull': False}
        elif self.value() == 'has_redelivery':
            filter_kwargs = {'redeliveries__isnull': False}
        elif self.value() == 'has_no_redelivery':
            filter_kwargs = {'redeliveries__isnull': True}
        else:
            return queryset
        return queryset.filter(**filter_kwargs)


def mark_for_redelivery(modeladmin, request, queryset):
    validate_func_list = [
        remove_unsupported_release_statuses,
        remove_duplicated_deliveries,
        remove_legacy_deliveries,
        remove_invalid_checksum_deliveries,
    ]

    filtered_queryset = queryset

    for func in validate_func_list:
        filtered_queryset = func(filtered_queryset, request)

    filtered_queryset.update(redeliver=True)


def unmark_for_redelivery(modeladmin, request, queryset):
    queryset.update(redeliver=False)


mark_for_redelivery.short_description = (
    "Mark selected batch_delivery_releases for Redelivery"
)
unmark_for_redelivery.short_description = (
    "Unmark selected batch_delivery_releases for Redelivery"
)


def remove_legacy_deliveries(queryset, request):
    return queryset.filter(
        Q(delivery__batch__isnull=False) | Q(delivery__channel=FUGA)
    ).exclude(delivery__channel=FUGA, type=BatchDeliveryRelease.DELIVERY_TYPE_INSERT)


# TODO probably good to allow same release but different stores
def remove_duplicated_deliveries(queryset, request):
    """
    We don't want to trigger multiple redeliveries for the same release so we order
    the duplicated by release_id and then just grab the most recent one.
    """
    filtered_queryset = queryset.order_by("release_id", "-id").distinct("release_id")
    removed_ids = get_removed_release_ids(queryset, filtered_queryset)

    if removed_ids:
        messages.add_message(
            request,
            messages.WARNING,
            "Removed duplicated redeliveries for release_ids. %s" % removed_ids,
        )

    return filtered_queryset


def remove_unsupported_release_statuses(queryset, request):
    """
    A release can have been taken down after this specific delivery that is marked
    for redelivery so we filter out unsupported statuses to be on the safe side.
    """
    filtered_queryset = queryset.filter(release__status__in=Release.APPROVED_STATUS_SET)
    removed_ids = get_removed_release_ids(queryset, filtered_queryset)

    if removed_ids:
        messages.add_message(
            request,
            messages.WARNING,
            "Removed redeliveries with invalid release.status for release_ids. %s"
            % removed_ids,
        )

    return filtered_queryset


def remove_invalid_checksum_deliveries(queryset, request):
    invalid_release_ids = []

    # Does not work to get releases directly from bdr.release here because of lazy
    # loading or something. Triggers `'NoneType' object has no attribute 'attname'`.
    # Probably because we're doing select_related and/or prefetch_related.
    releases = Release.objects.filter(
        pk__in=queryset.values_list("release_id", flat=True)
    )

    for release in releases:
        cover_art = release.cover_art
        verified_checksum = _calculate_django_file_checksum(cover_art.file)
        if verified_checksum != cover_art.checksum:
            invalid_release_ids.append(release.pk)

    filtered_queryset = queryset.exclude(release_id__in=invalid_release_ids)

    if invalid_release_ids:
        messages.add_message(
            request,
            messages.WARNING,
            "Removed redeliveries for invalid cover art checksum release_ids. %s"
            % invalid_release_ids,
        )

    return filtered_queryset


def get_removed_release_ids(queryset, filtered_queryset):
    removed_ids = None

    if queryset.count() != filtered_queryset.count():
        removed_ids = list(
            queryset.difference(filtered_queryset).values_list("release_id", flat=True)
        )

        # Needed to get diff for duplicated release_ids
        if not removed_ids:
            count = Counter(queryset.values_list("release_id", flat=True))
            removed_ids = [k for k, v in count.items() if v > 1]

    return removed_ids


@admin.register(BatchDeliveryRelease)
class BatchDeliveryReleaseAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'release_id',
        'delivery_id',
        'get_batch_id',
        'get_delivery_channel',
        'get_status_display',
        'get_type_display',
        'errors',
        'get_date_created',
        'is_redelivery',
        'has_redeliveries',
        'redeliver',
        'get_batch_user',
    )

    list_filter = (
        'status',
        'type',
        'delivery__channel',
        ReleaseBatchBoolFilter,
        'redeliver',
        RedeliveryFilter,
        ('delivery__date_created', DateFieldListFilter),
    )
    readonly_fields = (
        'delivery',
        'type',
        'status',
        'errors',
        'warnings',
        'stores',
        'redeliveries',
        'is_redelivery_for',
    )
    exclude = ('release',)
    raw_id_fields = ('delivery', 'redeliveries')
    actions = (mark_for_redelivery, unmark_for_redelivery)
    search_fields = ('id__exact', 'release__id__exact', 'delivery__id__exact')
    list_select_related = ('release', 'delivery', 'batch_delivery_release')

    def lookup_allowed(self, key, value):
        if key in ('delivery__batch__user_id'):
            return True
        return super().lookup_allowed(key, value)

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .select_related('delivery', 'delivery__batch')
            .prefetch_related('stores', 'excluded_stores')
        )

    def is_redelivery_for(self, obj):
        return list(obj.batchdeliveryrelease_set.values_list('id', flat=True))

    def is_redelivery(self, obj):
        return obj.batchdeliveryrelease_set.exists()

    def get_redelivery_ids(self, obj):
        return list(obj.redeliveries.values_list('id', flat=True))

    def has_redeliveries(self, obj):
        return obj.redeliveries.exists()

    def get_date_created(self, obj):
        return obj.delivery.date_created

    def get_batch_id(self, obj):
        if obj.delivery.batch:
            return obj.delivery.batch.id

    def get_batch_user(self, obj):
        if obj.delivery.batch:
            return obj.delivery.batch.user

    def get_delivery_channel(self, obj):
        return obj.delivery.get_channel_display()

    get_date_created.short_description = "Created"
    get_batch_id.short_description = "Batch ID"
    get_batch_user.short_description = "User"
    get_delivery_channel.short_description = "Channel"
    get_redelivery_ids.short_description = "Redeliveries"
    is_redelivery.boolean = True
    has_redeliveries.boolean = True

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(BatchDelivery)
class BatchDeliveryAdmin(admin.ModelAdmin):
    list_display = (
        'delivery_id',
        'channel',
        'number_of_releases',
        'status',
        'date_created',
        'get_batch',
    )
    list_filter = ('channel', 'status', BatchBoolFilter)
    list_select_related = ('batch',)
    inlines = (BatchDeliveryReleaseAdminInline,)
    fields = (
        'get_batch',
        'delivery_id',
        'channel',
        'status',
        'date_created',
        'date_updated',
    )
    readonly_fields = (
        'get_batch',
        'delivery_id',
        'channel',
        'status',
        'date_created',
        'date_updated',
    )

    search_fields = (
        'delivery_id__exact',
        'batchdeliveryrelease__release__upc__code__exact',
        'batchdeliveryrelease__release__id__exact',
    )

    def get_search_results(self, request, queryset, search_term):
        if search_term:
            deliveries_qs = BatchDelivery.objects.filter(
                Q(delivery_id__exact=search_term)
                | Q(batchdeliveryrelease__release__upc__code__exact=search_term)
                | Q(batchdeliveryrelease__release__id__exact=search_term)
            )
            return deliveries_qs, True
        return queryset, True

    def number_of_releases(self, instance):
        return instance.releases.count()

    def get_batch(self, instance):
        if instance.batch:
            url = reverse('admin:amuse_batch_change', args=(instance.batch.pk,))
            return mark_safe(f'<a href="{url}">{instance.batch}</a>')
        else:
            return mark_safe('No Batch')

    get_batch.short_description = "Batch"

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


class BatchDeliveryInline(admin.TabularInline):
    model = BatchDelivery
    readonly_fields = (
        'delivery_id',
        'channel',
        'release_count',
        'status',
        'date_created',
        'date_updated',
        'admin',
    )
    extra = 0

    def has_add_permission(self, request, obj):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def release_count(self, batch_delivery):
        return batch_delivery.releases.count()

    def admin(self, batch_delivery):
        url = reverse('admin:amuse_batchdelivery_change', args=(batch_delivery.pk,))
        return mark_safe(f'<a href="{url}">Admin...</a>')


@admin.register(Batch)
class BatchAdmin(admin.ModelAdmin):
    list_display = ('id', 'file', 'status', 'user', 'date_created', 'date_updated')
    readonly_fields = ('id', 'status', 'file', 'user', 'date_created', 'date_updated')
    inlines = (BatchDeliveryInline,)

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


class BulkDeliveryJobForm(forms.ModelForm):
    class Meta:
        model = BulkDeliveryJob
        fields = '__all__'

    help_texts = {
        BulkDeliveryJob.MODE_ADD_RELEASE_STORES: 'Adds the above selected stores on the releases and performs the bulk operation',
        BulkDeliveryJob.MODE_OVERRIDE_RELEASE_STORES: 'Just performs the bulk operation',
        BulkDeliveryJob.MODE_ONLY_RELEASE_STORES: 'Ignores the above selection of stores and performs the bulk operation on ALL release selected stores',
        # BulkDeliveryJob.MODE_ONLY_FUGA_RELEASE_STORES: 'Ignores the above selection of stores and performs the bulk operation on ALL release selected stores related to fuga',
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields['store'] = forms.ModelChoiceField(
            queryset=ordered_stores_queryset(
                exclude_stores=['instagram', 'amazon', 'twitch']
            ),
            required=False,
            help_text='Store to perform the bulk operation towards.',
        )
        self.fields['mode'] = forms.ChoiceField(
            choices=[
                (
                    key,
                    mark_safe(
                        f'<strong>{BulkDeliveryJob.MODE_OPTIONS[key]}</strong>  <d style="padding-left:1em;"></d>({self.help_texts[key]})'
                    ),
                )
                for key in self.help_texts
            ],
            required=True,
            widget=forms.RadioSelect,
            help_text='Mode of bulk operation',
        )
        self.fields['youtube_content_id'] = forms.ChoiceField(
            choices=Song.YT_CONTENT_ID_CHOICES,
            required=False,
            widget=forms.RadioSelect,
            help_text='Optional - select only if you want to update Youtube Content ID.',
        )
        self.fields['checks_to_override'] = forms.MultipleChoiceField(
            choices=((check.__name__, check.__name__) for check in ALL_DELIVERY_CHECKS),
            required=False,
            help_text='WARNING! This is to be used on a very rare occasion! Do not select any unless you know exactly what you are doing!',
        )


@admin.register(BulkDeliveryJob)
class BulkDeliveryJobAdmin(admin.ModelAdmin):
    form = BulkDeliveryJobForm
    list_display = (
        'id',
        'type',
        'mode',
        'input_file',
        'status',
        'description',
        'checks_to_override',
        'ignore_release_status',
        'unprocessed',
        'prevented',
        'failed',
        'successful',
        'total',
        'user',
        'execute_at',
        'date_created',
        'date_updated',
        'youtube_content_id',
    )
    list_filter = ('status', 'type', 'mode', ('user', admin.RelatedOnlyFieldListFilter))

    def get_readonly_fields(self, request, obj=None):
        return (
            [
                'id',
                'input_file',
                'type',
                'mode',
                'store',
                'status',
                'description',
                'checks_to_override',
                'ignore_release_status',
                'user',
                'execute_at',
                'date_created',
                'date_updated',
            ]
            if obj
            else []
        )

    def get_job_results(self, instance, status):
        url = reverse("admin:amuse_bulkdeliveryjobresult_changelist")
        num_results = BulkDeliveryJobResult.objects.filter(
            job=instance, status=status
        ).count()
        return mark_safe(
            f'<a href="{url}?job_id={instance.id}&status={status}">{num_results}</a>'
        )

    def has_delete_permission(self, request, obj=None):
        if obj is None:
            return True

        if obj.status != BulkDeliveryJob.STATUS_CREATED:
            return False

        if obj.execute_at is None:
            return False

        return True

    def save_model(self, request, obj, form, change):
        obj.user = request.user
        super().save_model(request, obj, form, change)

    def save_related(self, request, form, formsets, change):
        super().save_related(request, form, formsets, change)
        obj = form.instance
        if obj.status == BulkDeliveryJob.STATUS_CREATED and obj.execute_at is None:
            bulk_delivery_job_command.delay(obj.id)

    def successful(self, instance):
        return self.get_job_results(instance, BulkDeliveryJobResult.STATUS_SUCCESSFUL)

    successful.short_description = 'successful'
    successful.allow_tags = True

    def failed(self, instance):
        return self.get_job_results(instance, BulkDeliveryJobResult.STATUS_FAILED)

    failed.short_description = 'failed'
    failed.allow_tags = True

    def prevented(self, instance):
        return self.get_job_results(instance, BulkDeliveryJobResult.STATUS_PREVENTED)

    prevented.short_description = 'prevented'
    prevented.allow_tags = True

    def unprocessed(self, instance):
        return self.get_job_results(instance, BulkDeliveryJobResult.STATUS_UNPROCESSED)

    unprocessed.short_description = 'unprocessed'
    unprocessed.allow_tags = True

    def get_queryset(self, request):
        return BulkDeliveryJob.objects.annotate(total=Count('bulkdeliveryjobresult'))

    def total(self, obj):
        return obj.total

    total.short_description = 'total'
    total.admin_order_field = 'total'

    def get_urls(self):
        urls = super().get_urls()
        url_name_base = f'{self.model._meta.app_label}_{self.model._meta.model_name}'
        url_name_replace = f'{url_name_base}_add_multiple'

        urls = [
            path(
                'add-multiple/',
                self.add_multiple_bulk_delivery_jobs,
                name=url_name_replace,
            )
        ] + urls
        return urls

    def add_multiple_bulk_delivery_jobs(self, request):
        if request.method == 'POST':
            form = AddMultipleBulkDeliveryJobsForm(request.POST, request.FILES)
            if form.is_valid():
                input_stream = request.FILES['input_file']

                store = form.cleaned_data['store']
                type = form.cleaned_data['type']
                mode = form.cleaned_data['mode']

                start_at = form.cleaned_data['start_at']
                delay = form.cleaned_data['delay_between_chunks']
                row_limit = form.cleaned_data['chunk_size']

                for i, buffer in enumerate(
                    CsvSplitter.split_uploaded_file(input_stream, row_limit)
                ):
                    buffer.seek(0)
                    # Covert to bytes otherwise S3 file upload fails
                    # https://stackoverflow.com/questions/66902713/saving-file-like-object-to-s3-i-get-error-unicode-objects-must-be-encoded-befor
                    file_data = File(io.BytesIO(buffer.read().encode('utf-8')))

                    execute_at = start_at + timedelta(minutes=delay * i)
                    job = BulkDeliveryJob.objects.create(
                        type=type, mode=mode, user=request.user, execute_at=execute_at
                    )
                    job.input_file.save('', file_data, True)

                    url = reverse('admin:amuse_bulkdeliveryjob_change', args=[job.pk])
                    url_string = f'<a href="{url}" target="_blank">{job}</a>'
                    messages.info(
                        request, mark_safe(f'Bulk Delivery Job created: {url_string}')
                    )

                messages.info(request, mark_safe(f'Bulk Delivery Job(s) Created'))
                return HttpResponseRedirect(
                    reverse('admin:amuse_bulkdeliveryjob_changelist')
                )
        else:
            form = AddMultipleBulkDeliveryJobsForm()

        return render(
            request,
            'admin/amuse/bulkdeliveryjob/add_multiple_bulk_delivery_jobs_form.html',
            context={
                **self.admin_site.each_context(request),
                'form': form,
                'title': f'Import & split bulk delivery jobs',
                'media': self.media,
                'opts': self.model._meta,
            },
        )


class AddMultipleBulkDeliveryJobsForm(BulkDeliveryJobForm):
    chunk_size = forms.IntegerField(
        required=True,
        label='Chunk size',
        min_value=1,
        initial=200,
        help_text='Number of rows in each chunk.',
    )

    start_at = forms.DateTimeField(
        initial=datetime.now(tz=pytz.UTC).astimezone() + timedelta(minutes=5),
        help_text='First chunk will be processed at this time.',
    )

    delay_between_chunks = forms.IntegerField(
        required=True,
        label='Delay between chunks',
        min_value=1,
        initial=60,
        help_text='Delay (minutes) between starting two bulk delivery jobs.',
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['execute_at'].widget = forms.HiddenInput()

    def clean_start_at(self):
        now = datetime.now(tz=pytz.UTC).astimezone()
        start_at = self.cleaned_data['start_at']
        if start_at < now:
            raise forms.ValidationError("This field value has to be in the future.")
        return start_at


class BulkDeliveryJobResultResource(resources.ModelResource):
    class Meta:
        model = BulkDeliveryJobResult
        fields = ('release__id',)


@admin.register(BulkDeliveryJobResult)
class BulkDeliveryJobResultAdmin(ExportMixin, admin.ModelAdmin):
    list_display = (
        'id',
        'job_id',
        'release_id',
        'stores',
        'batch_id',
        'status',
        'description',
    )
    list_display_links = None

    readonly_fields = ('id', 'job', 'release', 'batch', 'status', 'description')

    list_filter = ('status', 'store')

    search_fields = ('job_id__exact', 'release_id__exact')

    resource_class = BulkDeliveryJobResultResource

    raw_id_fields = ('job', 'release', 'batch')

    def get_export_formats(self):
        self.formats = (base_formats.CSV,)
        return super().get_export_formats()

    def get_export_filename(self, request, queryset, file_format):
        return "{}.{}".format(str(uuid4()), file_format.get_extension())

    def stores(self, obj):
        if obj.store:
            return obj.store.name
        else:
            return 'selected stores'

    def job_id(self, obj):
        url = reverse('admin:amuse_bulkdeliveryjob_change', args=[obj.job_id])
        return mark_safe(f'<a href="{url}" target="_blank">{obj.job_id}</a>')

    def release_id(self, obj):
        url = reverse(
            'admin:contenttollgate_genericrelease_view', args=[obj.release_id]
        )
        return mark_safe(f'<a href="{url}" target="_blank">{obj.release_id}</a>')

    def batch_id(self, obj):
        if obj.batch_id:
            url = reverse('admin:amuse_batch_change', args=[obj.batch_id])
            return mark_safe(f'<a href="{url}" target="_blank">{obj.batch_id}</a>')
        else:
            return mark_safe('-')

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def save_model(self, request, obj, form, change):
        # Make sure user can't update/tamper with the results
        pass


@admin.register(NotificationTemplate)
class NotificationTemplateAdmin(admin.ModelAdmin):
    list_display = ('name', 'key')


@admin.register(Transcoding)
class TranscodingAdmin(admin.ModelAdmin):
    list_display = ('id', 'transcoder_job', 'status')
    list_filter = ('transcoder_name', 'status')
    search_fields = ('=song__id', '=song__release__id')
    readonly_fields = (
        'id',
        'transcoder_job',
        'transcoder_name',
        'status',
        'errors',
        'warnings',
        'release_id',
        'song_id',
    )
    exclude = ('song',)

    def release_id(self, object):
        return object.song.release.id

    def song_id(self, object):
        return object.song.id


@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = ('type', 'content_type', 'client', 'version', 'object')
    list_filter = ('type', 'client')
    readonly_fields = (
        'type',
        'client',
        'version',
        'ip',
        'country',
        'date_created',
        'object_id',
        'content_type',
        'object',
    )


@admin.register(Link)
class LinkAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'link', 'updated_at', 'created_at')
    readonly_fields = ('updated_at', 'created_at')
    search_fields = ('=id', '=name')


@admin.register(MinfraudResult)
class MinfraudResultAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'response_body',
        'fraud_score',
        'event_time',
        'event_type',
        'user',
        'release',
    )

    raw_id_fields = ('user', 'release')

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def get_actions(self, request):
        actions = super().get_actions(request)
        if 'delete_selected' in actions:
            del actions['delete_selected']
        return actions


@admin.register(FugaMetadata)
class FugaMetadataAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'release_id',
        'product_id',
        'status',
        'migration_wave',
        'revenue_level',
        'spotify_ready_to_migrate',
        'apple_ready_to_migrate',
        'ready_to_migrate',
        'has_spotify_ids',
        'spotify_roles_match',
        'metadata_match',
        'roles_match',
        'song_metadata_match',
        'song_roles_match',
        'has_alternative_stores',
        'whitelisted',
        'mark_to_be_deleted',
        'last_parsed_at',
        'last_synced_at',
        'delivery_history_extracted_at',
        'spotify_migration_started_at',
        'spotify_migration_completed_at',
        'migration_started_at',
        'migration_completed_at',
        'delete_started_at',
        'updated_at',
        'created_at',
    )

    list_filter = (
        'status',
        'metadata_match',
        'roles_match',
        'song_metadata_match',
        'song_roles_match',
        'has_spotify_ids',
        'spotify_roles_match',
    )

    search_fields = ('=release__id', '=product_id')

    raw_id_fields = ('release',)

    readonly_fields = (
        'id',
        'release_id',
        'product_id',
        'status',
        'spotify_ready_to_migrate',
        'ready_to_migrate',
        'has_spotify_ids',
        'spotify_roles_match',
        'metadata_match',
        'roles_match',
        'song_metadata_match',
        'song_roles_match',
        'whitelisted',
        'mark_to_be_deleted',
        'last_parsed_at',
        'last_synced_at',
        'delivery_history_extracted_at',
        'delete_started_at',
        'updated_at',
        'created_at',
        'release_metadata',
        'asset_metadata',
        'delivery_instructions_metadata',
        'spotify_metadata',
    )

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(FugaStores)
class FugaStoresAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'external_id',
        'name',
        'is_iip_dds',
        'is_ssf_dds',
        'has_delivery_service_support',
        'created_at',
    )

    search_fields = ('=id', 'name')

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(FugaDeliveryHistory)
class FugaDeliveryHistoryAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'external_id',
        'release_id',
        'product_id',
        'fuga_store',
        'ddex_batch_id',
        'action',
        'state',
        'executed_by',
        'dated_at',
        'created_at',
    )

    search_fields = (
        '=id',
        '=external_id',
        '=release__id',
        '=product_id',
        '=ddex_batch_id',
    )

    list_filter = ('action', 'state', 'fuga_store')

    def has_add_permission(self, request):
        return False


@admin.register(FugaPerson)
class FugaPersonAdmin(admin.ModelAdmin):
    list_display = ('id', 'external_id', 'name')
    readonly_fields = ('id', 'external_id', 'name')

    search_fields = ('=id', '=external_id', 'name')

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(FugaArtist)
class FugaArtistAdmin(admin.ModelAdmin):
    list_display = ('id', 'external_id', 'name', 'apple_id', 'spotify_id', 'parsed_at')
    readonly_fields = (
        'id',
        'external_id',
        'name',
        'apple_id',
        'spotify_id',
        'parsed_at',
    )

    search_fields = ('=id', '=external_id', 'name', '=apple_id', '=spotify_id')

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(FugaProductArtist)
class FugaProductArtistAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'release_id',
        'fuga_product_id',
        'sequence',
        'fuga_artist_id',
        'primary',
        'matched_artist_id',
        'spotify_id',
        'apple_id',
        'roles_match',
    )
    readonly_fields = (
        'id',
        'release_id',
        'fuga_product_id',
        'sequence',
        'fuga_artist_id',
        'primary',
        'matched_artist_id',
        'spotify_id',
        'apple_id',
        'roles_match',
    )

    list_filter = ('roles_match',)

    search_fields = (
        '=id',
        '=release_id',
        '=fuga_product_id',
        '=fuga_artist_id',
        '=spotify_id',
        '=apple_id',
    )

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(FugaAsset)
class FugaAssetAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'external_id',
        'isrc',
        'name',
        'genre',
        'language',
        'duration',
        'metadata_match',
        'roles_match',
    )

    readonly_fields = (
        'id',
        'external_id',
        'isrc',
        'name',
        'genre',
        'language',
        'duration',
        'metadata_match',
        'roles_match',
    )

    search_fields = ('=id', '=external_id', '=isrc', 'name')

    list_filter = ('metadata_match', 'roles_match')

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(FugaProductAssetArtist)
class FugaProductAssetArtistAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'release_id',
        'fuga_product_id',
        'fuga_asset_id',
        'sequence',
        'fuga_artist_id',
        'fuga_person_id',
        'role',
        'primary',
        'matched_artist_id',
        'spotify_id',
        'apple_id',
        'roles_match',
    )
    readonly_fields = (
        'id',
        'release_id',
        'fuga_product_id',
        'fuga_asset_id',
        'fuga_artist_id',
        'fuga_person_id',
        'sequence',
        'role',
        'primary',
        'matched_artist_id',
        'spotify_id',
        'apple_id',
        'roles_match',
    )

    search_fields = (
        '=id',
        '=release_id',
        '=fuga_product_id',
        '=fuga_asset_id',
        '=fuga_artist_id',
        '=spotify_id',
        '=apple_id',
    )

    list_filter = ('role', 'roles_match')

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(FugaMismatch)
class FugaMismatchAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'release_id',
        'fuga_product_id',
        'fuga_asset_id',
        'mismatch_attribute',
        'jarvis_value',
        'fuga_value',
    )
    readonly_fields = (
        'id',
        'release_id',
        'fuga_product_id',
        'fuga_asset_id',
        'mismatch_attribute',
        'jarvis_value',
        'fuga_value',
    )

    search_fields = ('=id', '=release_id', '=fuga_product_id', '=fuga_asset_id')

    list_filter = ('mismatch_attribute',)

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(FugaProductAsset)
class FugaProductAssetAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'release_id',
        'fuga_product_id',
        'fuga_asset_id',
        'sequence',
        'matched_song_id',
        'metadata_match',
        'roles_match',
        'spotify_roles_match',
        'has_spotify_ids',
    )
    readonly_fields = (
        'id',
        'release_id',
        'fuga_product_id',
        'fuga_asset_id',
        'sequence',
        'matched_song_id',
        'metadata_match',
        'roles_match',
        'spotify_roles_match',
        'has_spotify_ids',
    )

    search_fields = (
        '=id',
        '=release_id',
        '=fuga_product_id',
        '=fuga_asset_id',
        '=matched_song_id',
    )

    list_filter = ('metadata_match', 'roles_match', 'has_spotify_ids')

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(FugaGenre)
class FugaGenreAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'matched_genre_id')
    readonly_fields = ('id', 'name', 'matched_genre_id')

    search_fields = ('=id', '=name', '=matched_genre_id')

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(FugaMigrationWave)
class FugaMigrationWaveAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'description',
        'blocked',
        'marked',
        'deleted',
        'spotify_started',
        'spotify_completed',
        'started',
        'completed',
        'total',
    )
    readonly_fields = ('id',)
    search_fields = ('=id',)

    def get_wave_records_by_migration_status(self, instance, migration_status):
        url = reverse("admin:releases_fugametadata_changelist")
        params = {}
        if migration_status == MigrationStatus.DELETED:
            params = {"delete_started_at__isnull": 0}
        elif migration_status == MigrationStatus.COMPLETED:
            params = {
                "delete_started_at__isnull": 1,
                "migration_completed_at__isnull": 0,
            }
        elif migration_status == MigrationStatus.STARTED:
            params = {
                "delete_started_at__isnull": 1,
                "migration_completed_at__isnull": 1,
                "migration_started_at__isnull": 0,
            }
        elif migration_status == MigrationStatus.SPOTIFY_COMPLETED:
            params = {
                "delete_started_at__isnull": 1,
                "migration_completed_at__isnull": 1,
                "migration_started_at__isnull": 1,
                "spotify_migration_completed_at__isnull": 0,
            }
        elif migration_status == MigrationStatus.SPOTIFY_STARTED:
            params = {
                "delete_started_at__isnull": 1,
                "migration_completed_at__isnull": 1,
                "migration_started_at__isnull": 1,
                "spotify_migration_completed_at__isnull": 1,
                "spotify_migration_started_at__isnull": 0,
            }
        elif migration_status == MigrationStatus.MARKED:
            params = {
                "delete_started_at__isnull": 1,
                "migration_completed_at__isnull": 1,
                "migration_started_at__isnull": 1,
                "spotify_migration_completed_at__isnull": 1,
                "spotify_migration_started_at__isnull": 1,
                "ready_to_migrate__isnull": 0,
            }
        elif migration_status == MigrationStatus.BLOCKED:
            params = {
                "delete_started_at__isnull": 1,
                "migration_completed_at__isnull": 1,
                "migration_started_at__isnull": 1,
                "spotify_migration_completed_at__isnull": 1,
                "spotify_migration_started_at__isnull": 1,
                "ready_to_migrate__isnull": 1,
            }
        num_results = FugaMetadata.objects.filter(
            fuga_migration_wave=instance, **params
        ).count()
        return mark_safe(
            f'<a href="{url}?'
            f'fuga_migration_wave={instance.id}&'
            + urllib.parse.urlencode(params)
            + f'">{num_results}</a>'
        )

    def has_delete_permission(self, request, obj=None):
        return False

    def marked(self, instance):
        return self.get_wave_records_by_migration_status(
            instance, MigrationStatus.MARKED
        )

    marked.short_description = 'marked'
    marked.allow_tags = True

    def deleted(self, instance):
        return self.get_wave_records_by_migration_status(
            instance, MigrationStatus.DELETED
        )

    deleted.short_description = 'deleted'
    deleted.allow_tags = True

    def spotify_started(self, instance):
        return self.get_wave_records_by_migration_status(
            instance, MigrationStatus.SPOTIFY_STARTED
        )

    spotify_started.short_description = 'spotify started'
    spotify_started.allow_tags = True

    def spotify_completed(self, instance):
        return self.get_wave_records_by_migration_status(
            instance, MigrationStatus.SPOTIFY_COMPLETED
        )

    spotify_completed.short_description = 'spotify completed'
    spotify_completed.allow_tags = True

    def started(self, instance):
        return self.get_wave_records_by_migration_status(
            instance, MigrationStatus.STARTED
        )

    started.short_description = 'started'
    started.allow_tags = True

    def completed(self, instance):
        return self.get_wave_records_by_migration_status(
            instance, MigrationStatus.COMPLETED
        )

    completed.short_description = 'completed'
    completed.allow_tags = True

    def blocked(self, instance):
        return self.get_wave_records_by_migration_status(
            instance, MigrationStatus.BLOCKED
        )

    blocked.short_description = 'blocked'
    blocked.allow_tags = True

    def get_queryset(self, request):
        return FugaMigrationWave.objects.annotate(total=Count('fugametadata'))

    def total(self, instance):
        return instance.total

    total.short_description = 'total'
    total.admin_order_field = 'total'
