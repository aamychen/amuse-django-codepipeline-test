from django.contrib import admin

from codes.models import ISRC, UPC
from releases.models.song import Song


@admin.register(ISRC)
class AdminISRC(admin.ModelAdmin):
    list_display = ('id', 'code', 'status', 'licensed')
    search_fields = ('code',)

    change_form_template = "admin/isrc_changeform.html"

    def change_view(self, request, object_id, form_url='', extra_context=None):
        related_songs = Song.objects.filter(isrc__pk=object_id).order_by('release__id')

        extra_context = extra_context or {}
        extra_context['related_songs'] = related_songs

        return super().change_view(
            request, object_id, form_url, extra_context=extra_context
        )


@admin.register(UPC)
class AdminUPC(admin.ModelAdmin):
    list_display = ('id', 'code', 'status')
    search_fields = ('code',)
