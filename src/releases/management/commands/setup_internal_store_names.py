from django.core.management.base import BaseCommand

from releases.models import Store


STORES = (
    ('Amazon', 'amazon'),
    ('Anghami', 'anghami'),
    ('iTunes / Apple Music', 'apple'),
    ('Claro Música', 'claro_musica'),
    ('Deezer', 'deezer'),
    ('Facebook', 'facebook'),
    ('Google Music', 'google_music'),
    ('Instagram', 'instagram'),
    ('Napster', 'napster'),
    ('Nuuday', 'nuuday'),
    ('Shazam', 'shazam'),
    ('SoundCloud', 'soundcloud'),
    ('Spotify', 'spotify'),
    ('TIDAL', 'tidal'),
    ('TikTok', 'tiktok'),
    ('Twitch', 'twitch'),
    ('YouTube Content ID', 'youtube_content_id'),
    ('YouTube Music', 'youtube_music'),
)


class Command(BaseCommand):
    help = 'Setup Store.internal_name'

    def handle(self, *args, **kwargs):
        for name, internal_name in STORES:
            Store.objects.filter(name=name).update(internal_name=internal_name)
