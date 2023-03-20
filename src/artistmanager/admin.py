from django import forms
from django.shortcuts import render
from django.http import HttpResponseRedirect
from django.contrib import admin
from django.contrib import messages
from django.contrib.admin.helpers import ActionForm
from django.db.models import Q
from django.urls import path, reverse
from django.utils.safestring import mark_safe
from amuse.logging import logger
from users.models import User
from releases.models import SongArtistRole, RoyaltySplit
from artistmanager.utils import parse_input_string_to_digits

from users.admin import (
    HasOwnerListFilter,
    HasReleasesListFilter,
    IsSongContributorListFilter,
    UserArtistRoleInline,
)
from artistmanager.models import MoveArtist
from artistmanager.move_artists import MoveArtists


class NewOwnerActionForm(ActionForm):
    new_user = forms.IntegerField(label='NEW USER:', min_value=1, initial=1)


class InputFilter(admin.SimpleListFilter):
    template = 'admin/input_filter.html'

    def lookups(self, request, model_admin):
        # Dummy, required to show the filter.
        return ((),)

    def choices(self, changelist):
        # Grab only the "all" option.
        all_choice = next(super().choices(changelist))
        all_choice['query_parts'] = (
            (k, v)
            for k, v in changelist.get_filters_params().items()
            if k != self.parameter_name
        )
        yield all_choice


class ArtistFilter(InputFilter):
    parameter_name = 'artist'
    title = 'Artists IDs'

    def queryset(self, request, queryset):
        if self.value() is not None:
            ids = self.value()
            ids_list = parse_input_string_to_digits(ids)
            return queryset.filter(Q(id__in=ids_list))


@admin.register(MoveArtist)
class MoveArtistAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'name',
        'owner_link',
        'owner_tier',
        'owner_id',
        'created',
        'updated',
    )
    list_filter = (
        ArtistFilter,
        HasOwnerListFilter,
        HasReleasesListFilter,
        IsSongContributorListFilter,
    )

    search_fields = ('name', 'owner__id', 'owner__email', 'spotify_id')
    action_form = NewOwnerActionForm
    actions = [
        'move_artists',
        'check_for_pending_splits',
    ]
    fields = (
        'name',
        'owner',
        'image',
        'spotify_page',
        'twitter_name',
        'facebook_page',
        'instagram_name',
        'soundcloud_page',
        'youtube_channel',
        'apple_id',
        'spotify_id',
        'created',
        'updated',
    )
    readonly_fields = ('created', 'updated')
    raw_id_fields = ('owner',)
    inlines = (UserArtistRoleInline,)

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def get_actions(self, request):
        actions = super().get_actions(request)
        if 'delete_selected' in actions:
            del actions['delete_selected']
        return actions

    def changelist_view(self, request, extra_context=None):
        extra_context = {'title': 'Select ArtistV2 to move'}
        return super(MoveArtistAdmin, self).changelist_view(
            request, extra_context=extra_context
        )

    def owner_link(self, item):
        if not item.owner:
            return "-"
        user_url = reverse('admin:users_user_change', args=(item.owner.id,))
        user_link = '<a href="%s">%s</a>' % (user_url, item.owner.name)
        return mark_safe(user_link)

    def owner_tier(self, item):
        if not item.owner:
            return "-"
        return item.owner.subscription_tier

    owner_link.short_description = "Owner"

    def owner_id(self, item):
        if not item.owner:
            return "-"
        user_url = reverse('admin:users_user_change', args=(item.owner.id,))
        user_link = '<a href="%s">%s</a>' % (user_url, item.owner.id)
        return mark_safe(user_link)

    owner_id.short_description = "Owner ID"

    def move_artists(self, request, queryset):
        new_user = request.POST['new_user']
        new_user_id = int(new_user)
        artist_ids_list = [artist.id for artist in queryset]
        if not User.objects.filter(id=new_user_id).exists():
            self.message_user(
                request, (" %d User does not exit") % (new_user_id,), messages.ERROR
            )
            return HttpResponseRedirect(request.get_full_path())
        user = User.objects.get(id=new_user_id)
        if 'apply' in request.POST:
            logger.info(
                "Moving artist_id=%s to new user=%s" % (artist_ids_list, new_user)
            )
            mover = MoveArtists(artists_list=artist_ids_list, new_user_id=new_user_id)
            mover.execute_move_artists()
            self.message_user(
                request,
                (" %d artists moved successfully to new user") % (queryset.count(),),
                messages.SUCCESS,
            )
            return HttpResponseRedirect(request.get_full_path())
        return render(
            request,
            'admin/moveartist_intermediate.html',
            context={'artists': queryset, 'user': user},
        )

    def check_for_pending_splits(self, request, queryset):
        artist_ids_list = [artist.id for artist in queryset]
        songs = SongArtistRole.objects.values_list('song').filter(
            artist_id__in=artist_ids_list,
            role=SongArtistRole.ROLE_PRIMARY_ARTIST,
            artist_sequence=1,
        )
        splits_pending_count = RoyaltySplit.objects.filter(
            song__in=songs,
            status__in=[RoyaltySplit.STATUS_PENDING, RoyaltySplit.STATUS_CONFIRMED],
        ).count()
        if splits_pending_count > 0:
            self.message_user(request, ("There are PENDING SPLITS "), messages.WARNING)
        else:
            self.message_user(
                request, ("There is NO PENDING SPLITS "), messages.SUCCESS
            )
        return HttpResponseRedirect(request.get_full_path())
