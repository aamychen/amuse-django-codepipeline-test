import logging
import time
from datetime import datetime
from uuid import uuid4
from enum import Enum

from bitfield import BitField
from bitfield.forms import BitFieldCheckboxSelectMultiple
from django import forms
from django.conf import settings
from django.contrib import admin
from django.db.models import Exists, FileField, OuterRef
from django.http import JsonResponse, HttpResponseRedirect
from django.template.response import TemplateResponse
from django.urls import path, reverse
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from django.views.decorators.clickjacking import xframe_options_sameorigin
from django.views.decorators.csrf import csrf_exempt
from import_export import resources
from import_export.admin import ImportExportModelAdmin
from import_export.formats import base_formats
from nested_inline.admin import NestedModelAdmin, NestedStackedInline
from simple_history.admin import SimpleHistoryAdmin

from amuse import deliveries, tasks
from amuse.models.support import SupportEvent, SupportRelease
from amuse.services.transcoding import transcode
from amuse.tasks import _calculate_django_file_checksum
from amuse.widgets import AudioFileWidget
from contenttollgate.utils import generate_presigned_post
from releases.models import (
    AudibleMagicMatch,
    BlacklistedArtistName,
    Comments,
    CoverArt,
    Genre,
    MetadataLanguage,
    PlatformInfo,
    Release,
    ReleaseArtistRole,
    RoyaltySplit,
    Song,
    SongArtistRole,
    SongFile,
    Store,
    AssetLabel,
    ReleaseAssetLabel,
    SongAssetLabel,
)
from releases.models.release import ReleaseAsset
from releases.models.release_store_delivery_status import ReleaseStoreDeliveryStatus
from releases.utils import filter_song_file_flac
from releases.validators import validate_splits_for_songs
from subscriptions.models import Subscription, SubscriptionPlan


logger = logging.getLogger(__name__)


@admin.register(Store)
class StoreAdmin(admin.ModelAdmin):
    list_display = (
        'name',
        'active',
        'admin_active',
        'is_pro',
        'org_id',
        'logo',
        'category',
        'parent',
    )
    readonly_fields = ('internal_name', 'fuga_store')


class GenreInline(admin.TabularInline):
    model = Genre
    extra = 0
    verbose_name = 'Subgenre'
    verbose_name_plural = 'Subgenres'
    fields = ('name', 'status', 'apple_code', 'number_of_songs', 'number_of_releases')
    readonly_fields = ('number_of_songs', 'number_of_releases')

    def number_of_songs(self, instance):
        return format_html(
            '<a href="{0}?genre_id={1}">{2}</a>',
            reverse('admin:releases_song_changelist'),
            instance.id,
            instance.songs.count(),
        )
        # return len(instance.songs.all())

    def number_of_releases(self, instance):
        return format_html(
            '<a href="{0}?genre_id={1}">{2}</a>',
            reverse('admin:releases_release_changelist'),
            instance.id,
            instance.release_set.count(),
        )


@admin.register(Genre)
class AdminGenre(admin.ModelAdmin):
    list_display = ('name',)
    ordering = ('name',)
    inlines = (GenreInline,)

    def get_queryset(self, request):
        # Hack to only filter the queryset in genre change list view
        if request.path == reverse('admin:releases_genre_changelist'):
            return super(AdminGenre, self).get_queryset(request).filter(parent=None)
        return super(AdminGenre, self).get_queryset(request)


# --------------------------------------------------


class PlatformInfoInline(NestedStackedInline):
    model = PlatformInfo
    extra = 0


class SongArtistRoleInline(NestedStackedInline):
    model = SongArtistRole
    extra = 0
    fields = ('role', 'artist', 'artist_sequence')
    raw_id_fields = ('artist',)


class ReleaseArtistRolesFormSet(forms.models.BaseInlineFormSet):
    class Meta:
        model = ReleaseArtistRole
        fields = '__all__'

    def clean(self):
        for form in self.forms:
            if form.cleaned_data['id'] is not None:
                releaseartistrole = form.cleaned_data['id']

                role = form.cleaned_data['role']
                artist = form.cleaned_data['artist']
                sequence = form.cleaned_data['artist_sequence']

                main_primary_artist = form.cleaned_data['id'].main_primary_artist

                if (
                    releaseartistrole.role == role
                    and releaseartistrole.artist == artist
                    and releaseartistrole.artist_sequence == sequence
                ):
                    is_changed = False
                else:
                    is_changed = True

                if main_primary_artist is True:
                    if is_changed is True:
                        raise forms.ValidationError(
                            'You can not modify a Main Primary Artist'
                        )


class ReleaseArtistRolesInline(admin.StackedInline):
    formset = ReleaseArtistRolesFormSet
    model = ReleaseArtistRole
    extra = 0
    fields = ('role', 'artist', 'artist_sequence', 'main_primary_artist')
    raw_id_fields = ('artist',)
    readonly_fields = ['main_primary_artist']


class SongArtistRolesFormSet(forms.BaseModelFormSet):
    class Meta:
        model = SongArtistRole

    def clean(self):
        super().clean()

        if not self.is_valid():
            return

        sequence = [
            form.cleaned_data["artist_sequence"]
            for form in self.forms
            if form.cleaned_data and form.cleaned_data.get("DELETE", False) is False
        ]

        length = len(sequence) + 1

        if sorted(sequence) != [i for i in range(1, length)]:
            raise forms.ValidationError('Song artist role sequence is invalid!')

    def get_queryset(self):
        return super().get_queryset().order_by('artist_sequence')


class SongFileInline(NestedStackedInline):
    model = SongFile
    extra = 0
    formfield_overrides = {FileField: {'widget': AudioFileWidget}}


class AudibleMagicMatchInline(NestedStackedInline):
    model = AudibleMagicMatch
    extra = 0
    fields = ('track', 'album', 'artist')


class RoyaltySplitInline(NestedStackedInline):
    model = RoyaltySplit
    extra = 0
    fields = ('user', 'rate', 'start_date', 'end_date', 'status')
    readonly_fields = ('is_locked',)
    raw_id_fields = ('user',)

    def has_delete_permission(self, request, song=None):
        if song:
            return not song.has_locked_splits()
        return True

    def has_change_permission(self, request, song=None):
        if song:
            return not song.has_locked_splits()
        return True


class CoverArtInline(NestedStackedInline):
    model = CoverArt
    fields = ('file', ('width', 'height'), 'user')
    readonly_fields = ('width', 'height')
    raw_id_fields = ('user',)


class SongInline(NestedStackedInline):
    model = Song
    extra = 0
    inlines = (
        AudibleMagicMatchInline,
        SongFileInline,
        SongArtistRoleInline,
        RoyaltySplitInline,
    )
    raw_id_fields = ('isrc',)
    exclude = ('recording_place_id',)
    formfield_overrides = {BitField: {'widget': BitFieldCheckboxSelectMultiple}}


class CommentsInline(NestedStackedInline):
    model = Comments
    fields = ('text',)


class SubscriptionTierMapping(Enum):
    free = None
    plus = SubscriptionPlan.TIER_PLUS
    pro = SubscriptionPlan.TIER_PRO


def queryset_annotate_free(queryset):
    return (
        queryset.annotate(
            is_pro=Exists(
                Subscription.objects.active_for_date(date=OuterRef('created')).filter(
                    user=OuterRef('created_by')
                )
            )
        )
        .filter(is_pro=False)
        .distinct()
    )


def queryset_annotate_paid(queryset, tier_name):
    return (
        queryset.annotate(
            has_subscription=Exists(
                Subscription.objects.active_for_date(date=OuterRef('created')).filter(
                    user=OuterRef('created_by'),
                    plan__tier=SubscriptionTierMapping[tier_name].value,
                )
            )
        )
        .filter(has_subscription=True)
        .distinct()
    )


class SubscriptionTierFilter(admin.SimpleListFilter):
    title = 'sub_tier'
    parameter_name = 'sub_tier'

    def lookups(self, request, model_admin):
        return (('free', 'Free'), ('plus', 'Plus'), ('pro', 'Pro'))

    def queryset(self, _, queryset):
        value = self.value()
        try:
            tier_name = SubscriptionTierMapping[value].name
        except KeyError:
            return queryset

        if tier_name == SubscriptionTierMapping.free.name:
            return queryset_annotate_free(queryset)

        return queryset_annotate_paid(queryset, tier_name)


class AssigneeeRelatedOnlyFieldListFilter(admin.RelatedOnlyFieldListFilter):
    def field_choices(self, field, request, model_admin):
        pk_qs = (
            model_admin.get_queryset(request)
            .exclude(supportrelease__assignee__is_staff=False)
            .distinct()
            .values_list('%s__pk' % self.field_path, flat=True)
        )
        return field.get_choices(
            include_blank=False, limit_choices_to={'pk__in': pk_qs}
        )


class ReleaseModelForm(forms.ModelForm):
    class Meta:
        model = Release
        exclude = ('completed', 'approved', 'delivery_status')

    def clean(self):
        if self.cleaned_data[
            'schedule_type'
        ] == Release.SCHEDULE_TYPE_STATIC and not self.cleaned_data.get('release_date'):
            raise forms.ValidationError("Static releases must have a release date")


@admin.register(Release)
class AdminRelease(NestedModelAdmin, SimpleHistoryAdmin):
    list_filter = (
        'status',
        'user__category',
        ('supportrelease__assignee', AssigneeeRelatedOnlyFieldListFilter),
        SubscriptionTierFilter,
        'type',
        'schedule_type',
    )
    list_display = (
        'id',
        'name',
        'user',
        'type',
        'get_assignee',
        'get_subscription_tier',
        'schedule_type',
        'comments',
        'link',
        'apple_delivery_status',
        'status',
        'release_date',
        'updated',
    )
    history_list_display = ('release_status',)
    raw_id_fields = ('user', 'upc', 'created_by')
    inlines = (
        PlatformInfoInline,
        CoverArtInline,
        ReleaseArtistRolesInline,
        SongInline,
        CommentsInline,
    )
    actions = ['assign_releases']
    search_fields = (
        'name',
        'user__first_name',
        'user__last_name',
        'user__artist_name',
        'upc__code',
    )
    formfield_overrides = {BitField: {'widget': BitFieldCheckboxSelectMultiple}}
    form = ReleaseModelForm

    def get_urls(self):
        urls = super().get_urls()
        url_name_base = f'{self.model._meta.app_label}_{self.model._meta.model_name}'
        url_name_replace = f'{url_name_base}_splits'

        urls = [
            path(
                '<path:object_id>/splits/',
                self.admin_site.admin_view(self.edit_splits),
                name=url_name_replace,
            )
        ] + urls
        urls = [
            path(
                'validate-splits/',
                self.admin_site.admin_view(self.validate_splits),
                name=url_name_replace,
            )
        ] + urls
        return urls

    def edit_splits(self, request, object_id):
        release = Release.objects.get(id=object_id)
        song_ids = [s.id for s in release.songs.all()]
        validation_results = dict(validate_splits_for_songs(song_ids))
        del validation_results["SETTINGS"]
        context = {
            'release': release,
            'validation_results': validation_results,
            'opts': self.model._meta,
        }
        return TemplateResponse(request, 'admin/releases/edit_splits.html', context)

    def validate_splits(self, request):
        time_start = time.time()
        error = None
        song_ids = None
        validation_results = None
        start_date = request.POST.get("start_date")
        end_date = request.POST.get("end_date")

        if not start_date or not end_date:
            error = "You have to specify both a start and end date."
        else:
            start = datetime.strptime(start_date, "%Y-%m-%d")
            end = datetime.strptime(end_date, "%Y-%m-%d")
            date_range = (end - start).days

            if date_range > 365:
                error = "Can only validate a maximum of 365 days at a time."

            if start > end:
                error = "Start date must be before end date"

        if not error:
            song_ids = list(
                Release.objects.filter(
                    release_date__range=(start_date, end_date),
                    songs__isnull=False,
                    songs__royalty_splits__isnull=False,
                )
                .prefetch_related("songs")
                .values_list("songs__id", flat=True)
            )
            validation_results = dict(validate_splits_for_songs(song_ids))

        context = {
            'validation_results': validation_results,
            'start_date': start_date,
            'end_date': end_date,
            'error': error,
            'exec_time': time.time() - time_start,
            'opts': self.model._meta,
        }
        return TemplateResponse(request, 'admin/releases/validate_splits.html', context)

    def get_subscription_tier(self, release):
        if not release.created_by:
            return None

        return release.created_by.get_tier_display_for_date(release.created)

    get_subscription_tier.short_description = 'Subscription Tier'

    def release_status(self, obj):
        return obj.get_status_display()

    def get_assignee(self, release):
        if hasattr(release, 'supportrelease'):
            return release.supportrelease.assignee.name

        return None

    get_assignee.short_description = "Assigned To"

    def assign_releases(self, request, queryset):
        for release in queryset.all():
            if hasattr(release, 'supportrelease'):
                release.supportrelease.assignee = request.user
                release.supportrelease.save()
            else:
                SupportRelease.objects.create(release=release, assignee=request.user)

            SupportEvent.objects.create(
                event=SupportEvent.ASSIGNED, release=release, user=request.user
            )

    assign_releases.short_description = 'Assign to me'

    def post_slack_release_completed(self, request, queryset):
        for release in queryset:
            tasks.post_slack_release_completed.delay(release)

    post_slack_release_completed.short_description = 'Re-send completed notification'

    def apple_delivery_status(self, obj):
        bd = obj.batchdeliveryrelease_set.filter(
            delivery__channel=deliveries.APPLE
        ).last()
        if not bd:
            return None

        return mark_safe(
            f"<a href=\"{reverse('admin:amuse_batchdelivery_change', args=[bd.delivery.id])}\">{bd.get_status_display()}</a>"
        )


@admin.register(CoverArt)
class AdminCoverArt(admin.ModelAdmin):
    change_form_template = "admin/releases/checksum_changeform.html"
    raw_id_fields = ('user', 'release')
    readonly_fields = ('checksum',)
    exclude = ('images',)

    def change_view(self, request, object_id, form_url='', extra_context=None):
        obj = CoverArt.objects.get(pk=object_id)
        extra_context = extra_context or {}
        extra_context['stored_checksum'] = obj.checksum
        extra_context['verified_checksum'] = _calculate_django_file_checksum(obj.file)
        return super().change_view(
            request, object_id, form_url, extra_context=extra_context
        )

    def response_change(self, request, obj):
        if "regenerate_checksum" in request.POST and request.POST.get(
            "verified_checksum"
        ):
            old_checksum = obj.checksum
            new_checksum = request.POST["verified_checksum"]
            obj.checksum = new_checksum
            obj.save()
            logger.info(
                "Generated new checksum for coverart_id %s. "
                "Old checksum: %s, New checksum: %s"
                % (obj.id, old_checksum, new_checksum)
            )

            return HttpResponseRedirect(".")
        return super().response_change(request, obj)

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Song)
class AdminSong(admin.ModelAdmin):
    change_form_template = "admin/releases/checksum_changeform.html"
    get_model_perms = lambda self, req: {}
    raw_id_fields = ('isrc', 'release')
    formfield_overrides = {BitField: {'widget': BitFieldCheckboxSelectMultiple}}

    def change_view(self, request, object_id, form_url='', extra_context=None):
        obj = Song.objects.get(pk=object_id)
        flac_file = filter_song_file_flac(obj)
        extra_context = extra_context or {}
        extra_context['stored_checksum'] = flac_file.checksum
        extra_context['verified_checksum'] = _calculate_django_file_checksum(
            flac_file.file
        )
        return super().change_view(
            request, object_id, form_url, extra_context=extra_context
        )

    def response_change(self, request, obj):
        if "regenerate_checksum" in request.POST and request.POST.get(
            "verified_checksum"
        ):
            flac_file = filter_song_file_flac(obj)
            old_checksum = flac_file.checksum
            new_checksum = request.POST["verified_checksum"]
            flac_file.checksum = new_checksum
            flac_file.save()
            logger.info(
                "Generated new checksum for song_id %s. "
                "Old checksum: %s, New checksum: %s"
                % (obj.id, old_checksum, new_checksum)
            )

            return HttpResponseRedirect(".")
        return super().response_change(request, obj)

    def get_urls(self):
        urls = super().get_urls()
        url_name_base = f'{self.model._meta.app_label}_{self.model._meta.model_name}'
        url_name_replace = f'{url_name_base}_replace'
        url_name_prepare = f'{url_name_base}_prepare'
        url_name_complete = f'{url_name_base}_complete'

        urls = [
            path(
                '<path:object_id>/replace-audio-file/',
                self.admin_site.admin_view(self.replace_audio_file),
                name=url_name_replace,
            ),
            path(
                '<path:object_id>/replace-audio-file-prepare/',
                self.admin_site.admin_view(self.replace_audio_file_prepare),
                name=url_name_prepare,
            ),
            path(
                '<path:object_id>/replace-audio-file-complete/',
                self.admin_site.admin_view(self.replace_audio_file_complete),
                name=url_name_complete,
            ),
        ] + urls
        return urls

    @xframe_options_sameorigin
    def replace_audio_file(self, request, object_id):
        song = Song.objects.get(pk=object_id)
        context = {'song': song, 'opts': self.model._meta}
        return TemplateResponse(
            request, 'admin/contenttollgate/replace_audio_file.html', context
        )

    @csrf_exempt
    def replace_audio_file_prepare(self, request, object_id):
        return JsonResponse(
            generate_presigned_post(
                settings.AWS_SONG_FILE_UPLOADED_BUCKET_NAME, f'{str(uuid4())}.wav'
            )
        )

    @csrf_exempt
    def replace_audio_file_complete(self, request, object_id):
        transcode(Song.objects.get(pk=object_id), request.POST['key'])
        return JsonResponse({})


@admin.register(MetadataLanguage)
class AdminMetadataLanguage(admin.ModelAdmin):
    list_display = ('name', 'fuga_code', 'iso_639_1', 'iso_639_2')


@admin.register(RoyaltySplit)
class AdminRoyaltySplit(admin.ModelAdmin):
    list_filter = ('status',)
    list_display = (
        'song',
        'user',
        'percentage',
        'start_date',
        'end_date',
        'status',
        'created',
        'revision',
        'is_owner',
        'is_locked',
    )
    readonly_fields = ('is_locked',)
    search_fields = ('song__id', 'user__email')
    list_select_related = ('song', 'user')
    raw_id_fields = ('song', 'user')
    actions = ['set_is_owner', 'unset_is_owner']

    def percentage(self, obj):
        return '{0:.0%}'.format(obj.rate)

    def set_is_owner(self, request, queryset):
        queryset.update(is_owner=True)

    def unset_is_owner(self, request, queryset):
        queryset.update(is_owner=False)

    def has_delete_permission(self, request, split=None):
        if split:
            return not split.song.has_locked_splits()
        return True

    def has_change_permission(self, request, split=None):
        if split:
            return not split.song.has_locked_splits()
        return True


class BlacklistedArtistNameResource(resources.ModelResource):
    class Meta:
        model = BlacklistedArtistName
        fields = ('id', 'name')


@admin.register(BlacklistedArtistName)
class BlacklistedArtistNameAdmin(ImportExportModelAdmin):
    list_display = ('name', 'is_active', 'created', 'updated')
    list_filter = ('is_active',)
    search_fields = ('name',)
    readonly_fields = ('fuzzy_name',)
    resource_class = BlacklistedArtistNameResource

    def get_import_formats(self):
        """
        Returns available import formats.
        """
        self.formats = (base_formats.CSV,)
        return super().get_import_formats()

    def get_export_formats(self):
        """
        Returns available export formats.
        """
        self.formats = (base_formats.CSV,)
        return super().get_export_formats()


@admin.register(AssetLabel)
class AssetLabel(admin.ModelAdmin):
    list_display = ['name']


class ReleaseAssetLabelInline(NestedStackedInline):
    model = ReleaseAssetLabel
    extra = 0
    fields = ("asset_label",)
    raw_id_fields = ('release',)

    def get_formset(self, request, obj=None, **kwargs):
        formset = super().get_formset(request, obj, **kwargs)
        form = formset.form
        form.base_fields['asset_label'].widget.can_change_related = False
        form.base_fields['asset_label'].widget.can_delete_related = False

        return formset


class SongAssetLabelInline(NestedStackedInline):
    model = SongAssetLabel
    extra = 0
    fields = ("asset_label",)
    raw_id_fields = ('song',)

    def get_formset(self, request, obj=None, **kwargs):
        formset = super().get_formset(request, obj, **kwargs)
        form = formset.form
        form.base_fields['asset_label'].widget.can_change_related = False
        form.base_fields['asset_label'].widget.can_delete_related = False

        return formset


class SongAssetLabelsInline(SongInline):
    extra = 0
    max_num = 0
    inlines = (SongAssetLabelInline,)

    fieldsets = ((None, {'fields': (('name', 'id'),)}),)
    readonly_fields = ('name',)
    can_delete = False


@admin.register(ReleaseAsset)
class ReleaseAssetLabelsAdmin(AdminRelease):
    fieldsets = ((None, {'fields': ('user', ('name', 'label'))}),)
    readonly_fields = ('user', 'name', 'label')

    inlines = (ReleaseAssetLabelInline, SongAssetLabelsInline)

    def change_view(self, request, object_id=None, form_url='', extra_context=None):
        return super().change_view(
            request, object_id, form_url, extra_context=dict(show_delete=False)
        )

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(ReleaseStoreDeliveryStatus)
class ReleaseStoreDeliveryStatusAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'release',
        'store',
        'fuga_store',
        'status',
        'delivered_at',
        'verified',
        'dsp_release_id',
        'latest_delivery_log',
        'latest_fuga_delivery_log',
        'updated_at',
        'created_at',
    )

    readonly_fields = (
        'id',
        'release',
        'store',
        'fuga_store',
        'status',
        'delivered_at',
        'verified',
        'dsp_release_id',
        'latest_delivery_log',
        'latest_fuga_delivery_log',
        'updated_at',
        'created_at',
    )

    search_fields = ('=id', '=release__id')

    list_filter = ('store', 'fuga_store', 'status', 'verified')

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
