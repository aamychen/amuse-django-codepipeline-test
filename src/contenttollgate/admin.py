import logging
import time

from django.contrib import admin, messages
from django.contrib.admin.options import reverse
from django.contrib.messages import get_messages
from django.db.models import Count, Q
from django.db.models.expressions import Exists, OuterRef
from django.forms import modelformset_factory
from django.forms.forms import BaseForm
from django.forms.formsets import BaseFormSet
from django.http import HttpResponseRedirect, HttpResponseNotFound
from django.shortcuts import redirect
from django.template.response import TemplateResponse
from django.urls import path
from django.utils.safestring import mark_safe
from nested_inline.admin import NestedModelAdmin

from amuse import tasks
from amuse.models.event import Event
from amuse.models.support import SupportEvent, SupportRelease
from amuse.services.delivery.helpers import (
    create_batch_delivery_releases_list,
    get_started_deliveries,
    trigger_batch_delivery,
)
from amuse.services.release_delivery_info import ReleaseDeliveryInfo
from amuse.services.validation import validate
from amuse.support import (
    assign_pending_releases,
    assign_prepared_releases,
    count_pending_releases,
    count_prepared_releases,
)
from amuse.vendor.fuga.helpers import sync_fuga_delivery_data, perform_fuga_delete
from amuse.vendor.release_analysis.api import (
    get_results as get_release_analysis_results,
    ReleaseAnalysisApiError,
)
from contenttollgate.admin_filter import DirectDeliveryListFilter, ReleaseDateFilter
from contenttollgate.forms import CommentsForm
from contenttollgate.forms import ReleaseArtistRoleForm
from contenttollgate.forms import ReleaseForm
from contenttollgate.forms import SongArtistRoleForm
from contenttollgate.forms import SongForm
from contenttollgate.forms.coverart_form import CoverArtForm
from contenttollgate.forms.support_release_form import SupportReleaseForm
from contenttollgate.models import (
    ApprovedRelease,
    AssignedPendingRelease,
    AssignedPreparedRelease,
    DeliveredRelease,
    FreeRelease,
    GenericRelease,
    NotApprovedRelease,
    PendingRelease,
    PlusRelease,
    ProRelease,
    RejectedRelease,
)
from contenttollgate.utils import (
    get_users_info_for_release,
    enable_yt_content_id_for_release,
    disable_yt_content_id_for_release,
    get_alert_tag,
    show_audio_recognition_warning,
    get_selected_error_flags,
    trigger_release_updated_events,
    calculate_next_release,
    calculate_acr_warning_severity,
    write_release_history_log,
)
from releases.admin import SongArtistRolesFormSet
from releases.models import (
    CoverArt,
    Release,
    ReleaseArtistRole,
    Song,
    SongArtistRole,
    SongFile,
    Store,
    FugaMetadata,
)
from releases.models.fuga_metadata import FugaStatus
from releases.utils import filter_song_file_flac, ordered_stores_queryset
from subscriptions.models import Subscription, SubscriptionPlan
from users.models import User

logger = logging.getLogger(__name__)


class BaseAdmin(NestedModelAdmin):
    list_display = (
        'name',
        'get_artist_name',
        'get_user_email',
        'get_user_category',
        'schedule_type',
        'release_date',
        'comments',
        'created',
    )

    actions = None

    search_fields = (
        'name__icontains',
        'user__artist_name__icontains',
        'user__email__exact',
        'upc__code__exact',
    )

    class Media:
        css = {"all": ("admin/css/pending-release.css",)}

    def formfield_for_manytomany(self, db_field, request, **kwargs):
        if db_field.name == 'stores':
            release = Release.objects.get(pk=request.resolver_match.kwargs['object_id'])
            exclude_stores = ['audiomack'] if release.exclude_audiomack() else []
            kwargs['queryset'] = ordered_stores_queryset(exclude_stores=exclude_stores)
        return super(BaseAdmin, self).formfield_for_manytomany(
            db_field, request, **kwargs
        )

    def disable_yt_content_id(self, request, object_id):
        try:
            release = Release.objects.get(pk=object_id)
            disable_yt_content_id_for_release(release)
            message = f'Disabled CID monetization for Release {release.name}'
        except Store.DoesNotExist:
            message = f'YT CID Store not found, have the fixtures been loaded?'
            logger.error(message, exc_info=True)
        except Exception as e:
            message = f'An error occurred while disabling CID monetization for Release {release.pk if release else None}: {e}'
            logger.error(message, exc_info=True)
        finally:
            if request.method == 'POST':
                url_name = f"admin:{self.model._meta.app_label}_{self.model._meta.model_name}_view"
            else:
                url_name = f"admin:{self.model._meta.app_label}_{self.model._meta.model_name}_change"

            self.message_user(request, message)
            return HttpResponseRedirect(reverse(url_name, args=[release.pk]))

    def enable_yt_content_id(self, request, object_id):
        try:
            release = Release.objects.get(pk=object_id)
            enable_yt_content_id_for_release(release)
            message = f'Enabled CID monetization for Release {release.name}'
        except Store.DoesNotExist:
            message = f'YT CID Store not found, have the fixtures been loaded?'
            logger.error(message, exc_info=True)
        except Exception as e:
            message = f'An error occurred while enabling CID monetization for Release {release.pk if release else None}: {e}'
            logger.error(message, exc_info=True)
        finally:
            if request.method == 'POST':
                url_name = f"admin:{self.model._meta.app_label}_{self.model._meta.model_name}_view"
            else:
                url_name = f"admin:{self.model._meta.app_label}_{self.model._meta.model_name}_change"

            self.message_user(request, message)
            return HttpResponseRedirect(reverse(url_name, args=[release.pk]))

    def get_urls(self):
        urls = super().get_urls()
        url_name_direct_deliver = (
            f'{self.model._meta.app_label}_{self.model._meta.model_name}_direct_deliver'
        )
        url_name_view = (
            f'{self.model._meta.app_label}_{self.model._meta.model_name}_view'
        )
        url_name_assign = (
            f"{self.model._meta.app_label}_{self.model._meta.model_name}_assign"
        )
        url_change_status = (
            f"{self.model._meta.app_label}_{self.model._meta.model_name}_change_status"
        )
        url_refresh_release_warnings = f"{self.model._meta.app_label}_{self.model._meta.model_name}_refresh_warnings"
        url_name_disable_yt_content_id = f"{self.model._meta.app_label}_{self.model._meta.model_name}_disable_yt_content_id"
        url_name_enable_yt_content_id = f"{self.model._meta.app_label}_{self.model._meta.model_name}_enable_yt_content_id"
        urls = [
            path(
                '<path:object_id>/deliver/',
                self.admin_site.admin_view(self.deliver_release),
                name=url_name_direct_deliver,
            ),
            path(
                '<path:object_id>/change/',
                self.admin_site.admin_view(self.release_review_page),
                name=url_name_view,
            ),
            path(
                '<path:object_id>/view/',
                self.admin_site.admin_view(self.release_review_page),
                name=url_name_view,
            ),
            path(
                '<path:object_id>/enable_yt_content_id/',
                self.admin_site.admin_view(self.enable_yt_content_id),
                name=url_name_enable_yt_content_id,
            ),
            path(
                '<path:object_id>/disable_yt_content_id/',
                self.admin_site.admin_view(self.disable_yt_content_id),
                name=url_name_disable_yt_content_id,
            ),
            path(
                '<path:object_id>/refresh_warnings/',
                self.admin_site.admin_view(self.refresh_warnings),
                name=url_refresh_release_warnings,
            ),
            path("<path:object_id>/assign/", self.assign_release, name=url_name_assign),
            path(
                '<path:object_id>/change_status/',
                self.admin_site.admin_view(self.change_release_status),
                name=url_change_status,
            ),
        ] + urls

        return urls

    def deliver_release(self, request, object_id):
        release = Release.objects.get(pk=object_id)
        release_delivery_info = ReleaseDeliveryInfo(release)

        if request.method == 'POST':
            deliver_single = request.POST.get('deliver_single')
            deliver_all = request.POST.get('deliver_all')
            sync_fuga_data = request.POST.get('sync_fuga_data')

            if sync_fuga_data:
                fuga_release = FugaMetadata.objects.filter(release_id=object_id).first()
                if fuga_release:
                    sync_fuga_delivery_data([fuga_release], delay=10)

                # Refresh page after fuga sync to show latest info
                return HttpResponseRedirect(
                    reverse(
                        f"admin:{self.model._meta.app_label}_{self.model._meta.model_name}_direct_deliver",
                        args=[object_id],
                    )
                )

            if deliver_single:
                store, delivery_type = deliver_single.split(":")
                if store == "fuga":
                    self.handle_fuga_delivery(
                        release, release_delivery_info, delivery_type, request.user
                    )
                    return redirect(request.path_info)
                else:
                    stores = [store]

            elif deliver_all:
                delivery_type = deliver_all
                stores = release_delivery_info.get_direct_delivery_channels(
                    delivery_type
                )
                self.handle_fuga_delivery(
                    release, release_delivery_info, delivery_type, request.user
                )
            else:
                raise ValueError("Unsupported delivery method")

            direct_delivery_type = (
                'insert' if delivery_type == 'full_update' else delivery_type
            )
            self.trigger_release_delivery(
                direct_delivery_type, release, request.user, stores
            )

            return redirect(request.path_info)

        # warning logic
        has_valid_status_for_delivery = (
            release.status in Release.VALID_DELIVERY_STATUS_SET
        )
        has_valid_cover_art_checksum = self.has_valid_cover_art_checksum(release)
        has_valid_songs_checksum, invalid_songs = self.has_valid_songs_checksum(release)

        is_valid_for_delivery = all(
            [
                has_valid_status_for_delivery,
                has_valid_cover_art_checksum,
                has_valid_songs_checksum,
            ]
        )

        created_event = (
            Event.objects.content_object(release).type(type=Event.TYPE_CREATE).first()
        )

        main_artist_rar = ReleaseArtistRole.objects.filter(
            release=release, role=ReleaseArtistRole.ROLE_PRIMARY_ARTIST
        ).first()

        fuga_metadata = FugaMetadata.objects.filter(release=release).first()
        fuga_status = FugaStatus.NONE
        if fuga_metadata:
            if fuga_metadata.status == "DELETED" and fuga_metadata.delete_started_at:
                fuga_status = FugaStatus.DELETED
            elif (
                fuga_metadata.migration_started_at
                and not fuga_metadata.migration_completed_at
            ):
                fuga_status = FugaStatus.UNDER_MIGRATION
            elif fuga_metadata.migration_completed_at:
                fuga_status = FugaStatus.MIGRATED
            elif fuga_metadata.status == "PUBLISHED":
                fuga_status = FugaStatus.LIVE

        context = {
            'opts': self.model._meta,
            'release': release,
            'direct_delivery_stores': release_delivery_info.store_delivery_info,
            'fuga_stores': release_delivery_info.fuga_delivery_info,
            'is_valid_for_delivery': is_valid_for_delivery,
            'has_valid_status_for_delivery': has_valid_status_for_delivery,
            'has_valid_cover_art_checksum': has_valid_cover_art_checksum,
            'has_valid_songs_checksum': has_valid_songs_checksum,
            'invalid_songs': invalid_songs,
            'creator': release.created_by if release.created_by else release.user,
            'created_event': created_event,
            'main_artist': main_artist_rar.artist,
            'started_channels': get_started_deliveries(release.pk),
            'fuga_status': fuga_status.value,
        }

        return TemplateResponse(
            request,
            "admin/contenttollgate/delivery/direct_deliver_release.html",
            context,
        )

    def handle_fuga_delivery(self, release, release_delivery_info, delivery_type, user):
        fuga_release = FugaMetadata.objects.filter(release_id=release.id).first()
        fuga_stores = release_delivery_info.get_fuga_delivery_channels(delivery_type)

        if fuga_release and delivery_type == 'takedown':
            perform_fuga_delete(fuga_release)
        elif fuga_stores and delivery_type == 'full_update':
            self.trigger_release_delivery('update', release, user, fuga_stores)

    @staticmethod
    def trigger_release_delivery(delivery_type, release, user, stores):
        releases_list = create_batch_delivery_releases_list(
            delivery_type, [release], stores=stores
        )
        batch_id = trigger_batch_delivery(releases_list, user)
        logger.info(
            "User %s triggered batch %s for release %s from jarvi5",
            user.pk,
            batch_id,
            release.id,
        )

    def next_release(self, request, object_id):
        assigned_releases = self.model.objects.filter(
            status=Release.STATUS_PENDING,
            supportrelease__isnull=False,
            supportrelease__assignee=request.user,
        ).order_by("updated")

        if self.model == AssignedPendingRelease:
            assigned_releases = assigned_releases.filter(supportrelease__prepared=False)

        else:
            assigned_releases = assigned_releases.filter(supportrelease__prepared=True)

        if len(assigned_releases) == 0:
            messages.warning(request, f"Found no {self.model._meta.model_name}")

            return HttpResponseRedirect(
                reverse(
                    f'admin:{self.model._meta.app_label}_{self.model._meta.model_name}_changelist'
                )
            )
        next_release_id = calculate_next_release(
            int(object_id), list(assigned_releases.values_list('id', flat=True))
        )
        return HttpResponseRedirect(
            reverse(
                f'admin:{self.model._meta.app_label}_{self.model._meta.model_name}_view',
                args=[next_release_id],
            )
        )

    def release_review_page(self, request, object_id):
        SAR_EXTRA_FORMS = 10

        try:
            release = GenericRelease.objects.prefetch_related(
                'songs', 'comments', 'releaseartistrole_set'
            ).get(pk=object_id)
        except GenericRelease.DoesNotExist:
            return HttpResponseNotFound()

        coverart = CoverArt.objects.filter(release_id=object_id).first()
        release_artists_queryset = release.releaseartistrole_set.all()
        song_queryset = release.songs.all()

        comments = getattr(release, 'comments', None)
        support_release = getattr(release, 'supportrelease', None)
        assignee = (
            support_release.assignee
            if support_release and hasattr(support_release, 'assignee')
            else "-"
        )

        initial_release_status = release.status
        initial_prepared_status = support_release.prepared if support_release else None

        ReleaseArtistFormSet = modelformset_factory(
            ReleaseArtistRole, form=ReleaseArtistRoleForm, extra=10, can_delete=True
        )
        SongFormSet = modelformset_factory(Song, form=SongForm, extra=0)
        SongArtistRoleFormSet = modelformset_factory(
            SongArtistRole,
            form=SongArtistRoleForm,
            extra=SAR_EXTRA_FORMS,
            can_delete=True,
            formset=SongArtistRolesFormSet,
        )

        exclude_stores = ['audiomack'] if release.exclude_audiomack() else []
        release_form = ReleaseForm(
            request.POST or None,
            instance=release,
            stores_queryset=ordered_stores_queryset(exclude_stores=exclude_stores),
            prefix="release",
        )
        song_formset = SongFormSet(
            request.POST or None, queryset=song_queryset, prefix="song"
        )
        coverart_form = CoverArtForm(
            request.POST or None,
            request.FILES or None,
            instance=coverart,
            prefix="cover_art",
        )
        comments_form = CommentsForm(
            request.POST or None,
            instance=comments,
            prefix="release_comments",
            initial={"release": release} if not request.POST else None,
        )
        support_release_form = (
            SupportReleaseForm(
                request.POST or None, instance=support_release, prefix="support_release"
            )
            if support_release
            else None
        )

        song_artist_roles_formsets = {}
        for song in song_queryset:
            song_artist_roles_formsets[song.id] = SongArtistRoleFormSet(
                request.POST or None,
                prefix=f"song_artist_role_{song.id}",
                queryset=song.songartistrole_set.all(),
                initial=[{"song": song} for _ in range(SAR_EXTRA_FORMS)],
            )

        release_artist_roles_formset = ReleaseArtistFormSet(
            request.POST or None,
            queryset=release_artists_queryset,
            prefix="release_artist_roles",
            initial=[{"release": release}],
            form_kwargs={'song_artist_roles_formsets': song_artist_roles_formsets},
        )

        if request.method == 'POST':
            forms_list = [release_form, song_formset, coverart_form]

            if comments or (not comments and request.POST["release_comments-text"]):
                forms_list.append(comments_form)

            if support_release_form:
                forms_list.append(support_release_form)

            for song in song_queryset:
                forms_list.append(song_artist_roles_formsets[song.id])

            forms_list.append(release_artist_roles_formset)

            changed_forms = []
            changed_formsets = []

            if all([form.is_valid() for form in forms_list]):
                for form in forms_list:
                    if form.has_changed():
                        form.save()

                        if isinstance(form, BaseFormSet):
                            changed_formsets.append(form)
                        elif isinstance(form, BaseForm):
                            changed_forms.append(form)

                write_release_history_log(
                    request.user.pk, release, changed_forms, changed_formsets
                )

                trigger_release_updated_events(
                    release,
                    initial_release_status,
                    support_release,
                    initial_prepared_status,
                    request.user,
                )

                release_url = reverse(
                    f'admin:{self.model._meta.app_label}_{self.model._meta.model_name}_view',
                    args=[release.pk],
                )
                messages.success(
                    request,
                    mark_safe(
                        f"Successfully saved release: <a href='{release_url}'>{release.name}</a>"
                    ),
                )

                if request.POST.get('next') == "True":
                    return self.next_release(request, release.id)

                # If release status has changed redirect back to changelist view for model
                if initial_release_status != release.status:
                    return HttpResponseRedirect(
                        reverse(
                            f"admin:{self.model._meta.app_label}_{self.model._meta.model_name}_changelist"
                        )
                    )

                return HttpResponseRedirect(release_url)

            else:
                messages.error(request, "Failed to save")

        try:
            release_analysis_results = get_release_analysis_results(release.id)
        except (ReleaseAnalysisApiError, ValueError) as error:
            messages.warning(request, f"Failed to get release warnings: {error}")
            release_analysis_results = None

        songs = {
            song.id: {
                'name': song.name,
                'sequence': song.sequence,
                'artist_roles': song_artist_roles_formsets[song.id],
                'wav_file': song.files.filter(type=SongFile.TYPE_FLAC).first(),
                'mp3_file': song.files.filter(type=SongFile.TYPE_MP3).first(),
                'audio_matches': show_audio_recognition_warning(song),
                'explicit': song.explicit,
                'selected_error_flags': get_selected_error_flags(song),
                'acr_warning_severity': calculate_acr_warning_severity(
                    release_analysis_results, song.id
                ),
                'warnings': release_analysis_results['tracks'].get(song.id)
                if release_analysis_results
                else None,
            }
            for song in song_queryset
        }

        context = {
            'opts': self.model._meta,
            'release_form': release_form,
            'song_formset': song_formset,
            'release_artist_roles_formset': release_artist_roles_formset,
            'comments_form': comments_form,
            'coverart_form': coverart_form,
            'support_release_form': support_release_form,
            'release': release,
            'songs': songs,
            'coverart': coverart,
            'assignee': assignee,
            'yt_cid_status': release.songs.filter(
                youtube_content_id=Song.YT_CONTENT_ID_MONETIZE
            ).exists(),
            'main_artist': release.main_primary_artist,
            'users': get_users_info_for_release(release),
            'alert_tag': get_alert_tag(get_messages(request)),
            'selected_error_flags': get_selected_error_flags(release),
            'analysis_results': release_analysis_results,
        }

        return TemplateResponse(
            request, "admin/contenttollgate/release/view.html", context=context
        )

    def change_release_status(self, request, object_id):
        release = Release.objects.get(pk=object_id)
        status_list = dict((k, v) for (k, v) in Release.STATUS_CHOICES)

        if request.method == 'POST':
            new_status = request.POST.get('status')

            if new_status:
                new_status = int(new_status)

            if new_status in status_list.keys():
                release.status = new_status
                release.save()

            url_name = f'admin:{self.model._meta.app_label}_{self.model._meta.model_name}_change'
            return HttpResponseRedirect(reverse(url_name, args=[object_id]))

        context = {
            'opts': self.model._meta,
            'release': release,
            'status_list': status_list,
        }

        return TemplateResponse(
            request, "admin/contenttollgate/change_release_status.html", context
        )

    def refresh_warnings(self, request, object_id):
        release = Release.objects.get(pk=object_id)
        validate(release)

        # wait for warnings to update before redirecting
        time.sleep(3)

        return HttpResponseRedirect(
            reverse(
                f"admin:{self.model._meta.app_label}_{self.model._meta.model_name}_view",
                args=[object_id],
            )
        )

    def assign_release(self, request, object_id):
        release = Release.objects.get(pk=object_id)
        if hasattr(release, 'supportrelease'):
            release.supportrelease.assignee = request.user
            release.supportrelease.save()
        else:
            SupportRelease.objects.create(release=release, assignee=request.user)

        SupportEvent.objects.create(
            event=SupportEvent.ASSIGNED, release=release, user=request.user
        )
        if request.method == "POST":
            url_name = (
                f"admin:{self.model._meta.app_label}_{self.model._meta.model_name}_view"
            )
        else:
            url_name = f"admin:{self.model._meta.app_label}_{self.model._meta.model_name}_change"
        return HttpResponseRedirect(reverse(url_name, args=[release.pk]))

    def has_valid_cover_art_checksum(self, release):
        checksum = tasks._calculate_django_file_checksum(release.cover_art.file)

        if checksum != release.cover_art.checksum:
            logger.warning(
                "DD page delivery release %s coverart checksum error. %s is not %s"
                % (release.id, checksum, release.cover_art.checksum)
            )
            return False

        return True

    def has_valid_songs_checksum(self, release):
        error_list = []
        invalid_songs = []

        for song in release.songs.all().order_by('sequence'):
            flac_file = filter_song_file_flac(song)

            if flac_file.checksum is None:
                error_list.append("Song %s checksum is None" % song.id)
                invalid_songs.append(song.id)

        if error_list:
            logger.warning(
                "DD page delivery release %s song checksum errors %s"
                % (release.id, error_list)
            )
            return False, invalid_songs

        return True, invalid_songs

    def get_subscription_tier(self, release):
        if not release.created_by:
            return None

        return release.created_by.get_tier_display_for_date(release.created)

    get_subscription_tier.short_description = 'Subscription Tier'

    def get_user_category(self, release):
        return User.CATEGORY_CHOICES[release.user.category][1]

    get_user_category.short_description = 'User category'
    get_user_category.admin_order_field = 'user__category'

    def get_user_email(self, release):
        return release.user.email

    get_user_email.short_description = 'E-mail'
    get_user_email.admin_order_field = 'user__email'

    def get_artist_name(self, release):
        return release.main_primary_artist

    get_artist_name.short_description = 'Artist'
    get_artist_name.admin_order_field = 'user__artist_name'


class ReleaseAdmin(BaseAdmin):
    list_display = (
        'name',
        'status',
        'get_artist_name',
        'get_user_email',
        'get_user_category',
        'schedule_type',
        'get_subscription_tier',
        'release_date',
        'updated',
        'comments',
        'has_locked_splits',
        'get_status_change_link',
        'created',
    )
    list_per_page = 25

    def get_queryset(self, request):
        artist_id = request.GET.get('artist_id', None)
        if artist_id:
            result = GenericRelease.objects.filter(
                id__in=ReleaseArtistRole.objects.filter(artist_id=artist_id)
                .values('release')
                .union(
                    SongArtistRole.objects.filter(artist_id=artist_id).values(
                        'song__release'
                    )
                )
            ).order_by('-release_date')

            # avoid AttributeError("This QueryDict instance is immutable")
            request.GET = request.GET.copy()

            # remove artist_id to avoid additional filtering performed by changelist
            request.GET.pop('artist_id', None)

            return result

        return GenericRelease.objects.all().order_by('-release_date')

    def get_status_change_link(self, obj):
        url = f'admin:{self.model._meta.app_label}_{self.model._meta.model_name}_change_status'

        return mark_safe(
            '<a href="%s" target="_blank">Change status</a>'
            % reverse(url, args=(obj.id,))
        )

    get_status_change_link.short_description = "Change Status"


@admin.register(GenericRelease)
class GenericReleaseAdmin(ReleaseAdmin):
    list_display = (
        'name',
        'status',
        'get_artist_name',
        'get_user_email',
        'get_user_category',
        'get_subscription_tier',
        'schedule_type',
        'release_date',
        'updated',
        'comments',
        'has_locked_splits',
        'get_status_change_link',
        'created',
    )

    def get_search_results(self, request, queryset, search_term):
        if search_term:
            releases_qs = GenericRelease.objects.filter(
                Q(name__icontains=search_term)
                | Q(user__artist_name__icontains=search_term)
                | Q(user__email__exact=search_term)
                | Q(upc__code__exact=search_term)
            ).order_by('-release_date')
            return (releases_qs, True)
        return queryset, True


class AssignedReleaseAdmin(ReleaseAdmin):
    list_display = (
        'name',
        'get_subscription_tier',
        'status',
        'type',
        'get_artist_name',
        'get_user_email',
        'get_user_category',
        'schedule_type',
        'release_date',
        'updated',
        'comments',
        'created',
    )

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("supportrelease")

    def assign_releases(self, request):
        user_id = request.user.id

        tier = User.TIER_FREE
        if request.GET.get('subscription') == 'pro':
            tier = SubscriptionPlan.TIER_PRO
        elif request.GET.get('subscription') == 'plus':
            tier = SubscriptionPlan.TIER_PLUS

        language = None
        if request.GET.get('language') == 'spanish':
            language = 'spanish'
        elif request.GET.get('language') == 'non-spanish':
            language = 'non-spanish'

        if 'prepared' in request.GET:
            handler = assign_prepared_releases
            release_status = 'prepared %s' % request.GET.get('subscription')
        else:
            handler = assign_pending_releases
            release_status = 'pending %s' % request.GET.get('subscription')

        logger.info(f'Assigning {release_status} releases to user {user_id}')
        assigned = handler(
            count=10,
            user=request.user,
            sorting=request.GET.get('sort', None),
            tier=tier,
            language=language,
        )
        if assigned > 0:
            self.message_user(request, f'You were assigned {assigned} releases')
            logger.info(
                f'{assigned} {release_status} releases were assigned successfully to user {user_id}'
            )
        else:
            self.message_user(request, f'Please try again')
            logger.info(
                f'{release_status} releases failed to be assigned to user {user_id}'
            )

        return HttpResponseRedirect('../')


@admin.register(AssignedPendingRelease)
class AssignedPendingReleaseAdmin(AssignedReleaseAdmin):
    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .filter(
                status=Release.STATUS_PENDING,
                supportrelease__isnull=False,
                supportrelease__assignee=request.user,
                supportrelease__prepared=False,
            )
        )

    def changelist_view(self, request, extra_context=None):
        extra_context = extra_context or {}
        extra_context['pending_release_count'] = count_pending_releases(User.TIER_FREE)
        extra_context['pending_plus_release_count'] = count_pending_releases(
            SubscriptionPlan.TIER_PLUS
        )
        extra_context['pending_pro_release_count'] = count_pending_releases(
            SubscriptionPlan.TIER_PRO
        )
        return super(AssignedReleaseAdmin, self).changelist_view(request, extra_context)

    def get_urls(self):
        return [
            path('assign/', self.assign_releases, name='assign_pending_releases')
        ] + super(AssignedPendingReleaseAdmin, self).get_urls()


@admin.register(AssignedPreparedRelease)
class AssignedPreparedReleaseAdmin(AssignedReleaseAdmin):
    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .filter(
                status=Release.STATUS_PENDING,
                supportrelease__isnull=False,
                supportrelease__assignee=request.user,
                supportrelease__prepared=True,
            )
        )

    def changelist_view(self, request, extra_context=None):
        extra_context = extra_context or {}
        extra_context['prepared_release_count'] = count_prepared_releases(
            User.TIER_FREE
        )
        extra_context['prepared_plus_release_count'] = count_prepared_releases(
            SubscriptionPlan.TIER_PLUS
        )
        extra_context['prepared_pro_release_count'] = count_prepared_releases(
            SubscriptionPlan.TIER_PRO
        )
        return super(AssignedReleaseAdmin, self).changelist_view(request, extra_context)

    def get_urls(self):
        return [
            path('assign/', self.assign_releases, name='assign_prepared_releases')
        ] + super(AssignedPreparedReleaseAdmin, self).get_urls()


@admin.register(PendingRelease)
class PendingReleaseAdmin(ReleaseAdmin):
    list_display = (
        'name',
        'status',
        'get_artist_name',
        'get_user_email',
        'get_user_category',
        'get_acrcloud_count',
        'schedule_type',
        'release_date',
        'updated',
        'created',
        'comments',
    )

    def get_acrcloud_count(self, obj):
        return obj.acrcloud_match_count

    get_acrcloud_count.short_description = 'ACRCloud'
    get_acrcloud_count.admin_order_field = 'acrcloud_match_count'

    def get_queryset(self, request):
        return (
            PendingRelease.objects.filter(status=PendingRelease.STATUS_PENDING)
            .order_by('-release_date')
            .annotate(acrcloud_match_count=Count('songs__acrcloud_matches'))
        )


class BaseReleaseAdmin(BaseAdmin):
    is_pro = None
    model = None
    list_filter = [ReleaseDateFilter, 'schedule_type']
    actions = ['assign_to_me']

    list_display = (
        'name',
        'status',
        'get_artist_name',
        'get_user_email',
        'get_user_category',
        'get_subscription_tier',
        'schedule_type',
        'release_date',
        'updated',
        'created',
        'get_assignee',
        'comments',
    )

    def get_assignee(self, release):
        return (
            release.supportrelease.assignee if release.support_release_count else None
        )

    get_assignee.short_description = "Assignee"

    def get_queryset(self, request):
        queryset = self.model.objects.filter(status=self.model.STATUS_PENDING).order_by(
            'release_date'
        )

        if self.subscription_tier is None:  # free releases
            queryset = queryset.annotate(
                is_pro=Exists(
                    Subscription.objects.active_for_date(
                        date=OuterRef('created')
                    ).filter(user=OuterRef('created_by'))
                )
            ).filter(is_pro=False)
        else:  # filter by subscription tier
            queryset = queryset.annotate(
                has_subscription=Exists(
                    Subscription.objects.active_for_date(
                        date=OuterRef('created')
                    ).filter(
                        user=OuterRef('created_by'), plan__tier=self.subscription_tier
                    )
                )
            ).filter(has_subscription=True)

        return queryset.select_related('supportrelease').annotate(
            support_release_count=Count('supportrelease__release')
        )

    def assign_to_me(self, request, queryset):
        count = 0
        for release in queryset:
            if not release.support_release_count:
                SupportRelease.objects.create(release=release, assignee=request.user)
            else:
                SupportRelease.objects.filter(release=release).update(
                    assignee=request.user
                )
            SupportEvent.objects.create(
                event=SupportEvent.ASSIGNED, release=release, user=request.user
            )
            count += 1
        self.message_user(
            request,
            f'You were assigned {count} {"pro" if self.is_pro else "free"} ' 'releases',
        )


@admin.register(FreeRelease)
class FreeReleaseAdmin(BaseReleaseAdmin):
    subscription_tier = None
    model = FreeRelease


@admin.register(ProRelease)
class ProReleaseAdmin(BaseReleaseAdmin):
    subscription_tier = SubscriptionPlan.TIER_PRO
    model = ProRelease


@admin.register(PlusRelease)
class PlusReleaseAdmin(BaseReleaseAdmin):
    subscription_tier = SubscriptionPlan.TIER_PLUS
    model = PlusRelease


@admin.register(ApprovedRelease)
class ApprovedReleaseAdmin(BaseAdmin):
    actions = ['deliver_all', 'deliver_spotify', 'deliver_fuga']
    list_display = (
        'name',
        'get_artist_name',
        'get_user_email',
        'get_user_category',
        'schedule_type',
        'release_date',
        'updated',
        'created',
        'comments',
    )
    list_filter = [DirectDeliveryListFilter, 'schedule_type']

    def get_queryset(self, request):
        return ApprovedRelease.objects.filter(
            status=RejectedRelease.STATUS_APPROVED
        ).order_by('-release_date')

    def get_actions(self, request):
        actions = super().get_actions(request)

        if 'delete_selected' in actions:
            del actions['delete_selected']

        return actions


@admin.register(NotApprovedRelease)
class NotApprovedReleaseAdmin(BaseAdmin):
    def get_queryset(self, request):
        return NotApprovedRelease.objects.filter(
            status=NotApprovedRelease.STATUS_NOT_APPROVED
        ).order_by('-release_date')


@admin.register(RejectedRelease)
class RejectedReleaseAdmin(BaseAdmin):
    def get_queryset(self, request):
        return RejectedRelease.objects.filter(
            status=RejectedRelease.STATUS_REJECTED
        ).order_by('-release_date')


@admin.register(DeliveredRelease)
class DeliveredReleaseAdmin(BaseAdmin):
    actions = ['deliver_spotify', 'deliver_fuga']
    list_filter = [DirectDeliveryListFilter]

    def get_queryset(self, request):
        return DeliveredRelease.objects.filter(
            status=DeliveredRelease.STATUS_DELIVERED
        ).order_by('-release_date')

    def get_actions(self, request):
        actions = super(DeliveredReleaseAdmin, self).get_actions(request)

        if 'delete_selected' in actions:
            del actions['delete_selected']

        return actions
