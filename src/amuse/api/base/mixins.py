from rest_framework.exceptions import PermissionDenied, NotFound

from users.models import ArtistV2, UserArtistRole


class ArtistAuthorizationMixin:
    def get_authorized_artist(self, artist_id, user_id):
        try:
            artist = ArtistV2.objects.get(pk=artist_id)
        except ArtistV2.DoesNotExist:
            raise NotFound(detail='Artist not found')
        if not artist.is_accessible_by_admin_roles(user_id):
            raise PermissionDenied()
        return artist

    def get_authorized_artist_with_release_permission(self, artist_id, user_id):
        artist = ArtistV2.objects.filter(pk=artist_id).first()
        if not artist:
            return None

        roles_allowed = [
            UserArtistRole.SUPERADMIN,
            UserArtistRole.ADMIN,
            UserArtistRole.OWNER,
            UserArtistRole.MEMBER,
        ]
        return artist if artist.is_accessible_by(user_id, roles_allowed) else None
