from datetime import timedelta, datetime

from django.contrib.admin import SimpleListFilter
from django.template.defaulttags import register
from django.utils import timezone

from releases.models import Store, Song
from users.models import User


class DirectDeliveryListFilter(SimpleListFilter):
    title = 'direct delivery stores'
    parameter_name = 'store'

    def lookups(self, request, model_admin):
        return (('spotify', 'Spotify'), ('apple', 'Apple Music & iTunes'))

    def queryset(self, request, queryset):
        store = None

        if self.value() == 'spotify':
            store = Store.objects.filter(name='Spotify').first()
        elif self.value() == 'apple':
            store = Store.objects.filter(name='iTunes / Apple Music').first()

        if store:
            return queryset.filter(stores__in=[store])


class ReleaseDateFilter(SimpleListFilter):
    title = 'Release Date'
    parameter_name = 'release_date'

    def lookups(self, request, model_admin):
        return [(4, '4 days'), (7, '7 days'), (14, '14 days')]

    def queryset(self, request, queryset):
        if self.value() is not None:
            queryset = queryset.filter(
                release_date__lte=timezone.now() + timedelta(days=int(self.value()))
            )
        return queryset


@register.filter
def get_item(dictionary, key):
    return dictionary.get(key)


@register.filter
def starts_with(text: str, element: str):
    return text.startswith(element)


@register.filter
def get_song_file_url(dictionary, key):
    item = dictionary.get(key)
    if item and hasattr(item, 'file'):
        return item.file.url
    else:
        return None


@register.filter
def get_song_sequence(dictionary, key):
    item = dictionary.get(key)
    if item:
        return item.get('sequence')
    else:
        return None


@register.filter
def show_profanity_warning(songs, warning):
    track_id = warning.get("track_id")
    if track_id:
        song = songs.get(track_id)
        if song and song['explicit'] == Song.EXPLICIT_TRUE:
            return False

    return True


@register.filter
def get_track_duration(acr_result):
    duration_ms = acr_result.get('duration_ms')

    if duration_ms:
        seconds = int((duration_ms / 1000) % 60)
        minutes = int(duration_ms / (1000 * 60))
        return f"{minutes}:{seconds}"
    else:
        return "Unknown"


@register.filter
def generate_spotify_url_from_uri(uri):
    try:
        split_uri = uri.split(":")
        return f"https://open.spotify.com/{split_uri[1]}/{split_uri[2]}"
    except IndexError:
        return ""


@register.filter
def get_management_form(form):
    return form.management_form


@register.filter
def non_form_errors(formset):
    return formset.non_form_errors()


@register.filter
def convert_datetime(datetime_s):
    try:
        return datetime.utcfromtimestamp(datetime_s).strftime('%Y-%m-%d %H:%M:%S')
    except:
        return datetime_s


@register.filter
def get_user_category_symbol(category):
    category_symbols = {
        User.CATEGORY_DEFAULT: '✔️',
        User.CATEGORY_FLAGGED: '🔴',
        User.CATEGORY_PRIORITY: '🚨',
        User.CATEGORY_QUALIFIED: '✅',
    }
    return category_symbols[category]


@register.filter
def has_multiple_warnings(warnings):
    num_of_warnings = len(
        [
            warning
            for warning in warnings
            if warning.get('show_warning') and warning.get('track_id')
        ]
    )
    return num_of_warnings > 1


@register.filter
def calculate_comment_box_lines(text):
    number_of_lines = text.count('\n') + 1
    if number_of_lines < 4:
        return number_of_lines
    else:
        return 4
