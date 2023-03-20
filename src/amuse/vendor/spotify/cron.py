from datetime import datetime, timedelta

from django.db.models import Count, Q

from releases.models import Release
from slayer.clientwrapper import users_spotifyartist
from users.models import User


def fetch_users_eligible_for_backfill(limit=50000):
    """Returns backfill candidates as a list of ids"""
    ids = (
        User.objects.annotate(
            active_releases=Count(
                'releases',
                filter=Q(releases__status=Release.STATUS_RELEASED)
                & Q(releases__release_date__gte=datetime.today() - timedelta(days=90)),
            )
        )
        .filter(active_releases__gte=1, spotify_id__isnull=True)
        .values_list('id', flat=True)[:limit]
    )
    return list(ids)


def filter_related_users(ids, size):
    """Creates chunks of the given IDs, then passes along to slayer for resolution,
    then yields from the result"""
    for i in range(0, len(ids), size):
        results = users_spotifyartist(ids[i : i + size])
        if not results or 'users_to_spotify_artists' not in results:
            continue

        yield from results['users_to_spotify_artists']


def get_prepared_users(user_ids, resolve_chunk_size):
    """Validates items in the result and yields spotify-associated User objects"""
    amuse_spotify_users = {}
    for item in filter_related_users(user_ids, resolve_chunk_size):
        if 'user_id' not in item or 'id' not in item:
            continue

        amuse_user_id, spotify_user_id = int(item['user_id']), item['id']
        amuse_spotify_users[amuse_user_id] = spotify_user_id

    for user in User.objects.filter(id__in=amuse_spotify_users.keys()):
        user.spotify_id = amuse_spotify_users.get(user.id)
        yield user


def backfill_eligible_users(limit=50000):
    """Performs a bulk backfill of Spotify-associated users"""
    ids = [str(i) for i in fetch_users_eligible_for_backfill(limit)]
    users = get_prepared_users(ids, resolve_chunk_size=100)
    User.objects.bulk_update(users, fields=['spotify_id'], batch_size=500)
