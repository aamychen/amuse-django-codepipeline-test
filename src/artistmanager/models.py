from amuse.db.decorators import with_history
from users.models import ArtistV2


@with_history
class MoveArtist(ArtistV2):
    class Meta:
        proxy = True
