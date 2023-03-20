from uuid import uuid4
from django.db import transaction
from django.utils import timezone
from users.models import (
    User,
    ArtistV2,
    UserArtistRole,
)
from releases.models import Release, RoyaltySplit, SongArtistRole, ReleaseArtistRole
from amuse.logging import logger


class MoveArtists:
    def __init__(self, artists_list, new_user_id):
        self.artists_list = artists_list
        self.new_user_id = new_user_id
        self.new_user = User.objects.get(id=self.new_user_id)
        self.id = uuid4()

    def get_artist_old_user_map(self):
        artist_old_user_map = {}
        artists = ArtistV2.objects.filter(id__in=self.artists_list)
        for artist in artists:
            artist_old_user_map[artist.id] = artist.owner
        return artist_old_user_map

    def song_have_pending_splits(self, song):
        splits_count = RoyaltySplit.objects.filter(
            song=song,
            status__in=[RoyaltySplit.STATUS_PENDING, RoyaltySplit.STATUS_CONFIRMED],
        ).count()
        return splits_count > 0

    def get_splits_for_update(self, artist_id):
        songs_no_pending_splits = []
        sars = SongArtistRole.objects.filter(
            artist_id=artist_id,
            role=SongArtistRole.ROLE_PRIMARY_ARTIST,
            artist_sequence=1,
        )
        for sar in sars:
            if not self.song_have_pending_splits(sar.song):
                songs_no_pending_splits.append(sar.song)
        return RoyaltySplit.objects.filter(song__in=songs_no_pending_splits)

    def update_artist_v2_to_new_user(self):
        ArtistV2.objects.filter(id__in=self.artists_list).update(owner=self.new_user)

    def change_old_user_to_admin(self, artist_id, user):
        UserArtistRole.objects.filter(artist_id=artist_id, user=user).update(
            type=UserArtistRole.ADMIN
        )

    def add_new_user_as_owner(self, artist_id):
        if UserArtistRole.objects.filter(
            artist_id=artist_id, user=self.new_user
        ).exists():
            UserArtistRole.objects.filter(
                artist_id=artist_id, user=self.new_user
            ).update(type=UserArtistRole.OWNER)
            return
        UserArtistRole.objects.create(
            user=self.new_user, artist_id=artist_id, type=UserArtistRole.OWNER
        )

    def update_split(self, old_split, new_user, old_user):
        # Skipp PENDING/CONFIRMED/ARCHIVED splits
        if old_split.status != RoyaltySplit.STATUS_ACTIVE:
            return

        if old_split.user == old_user:
            # create new new split for new owner
            new_split = RoyaltySplit.objects.create(
                song=old_split.song,
                status=old_split.status,
                user=new_user,
                rate=old_split.rate,
                start_date=timezone.now(),
                end_date=None,
                revision=old_split.revision + 1,
            )

            new_split.is_owner = True
            new_split.save()
            logger.info(
                "trid= %s New split created (OWNER) id= %s " % (self.id, new_split.id)
            )

        if old_split.user != old_user:
            # create new splits for no owner user
            new_split = RoyaltySplit.objects.create(
                song=old_split.song,
                status=old_split.status,
                user=old_split.user,
                rate=old_split.rate,
                start_date=timezone.now(),
                revision=old_split.revision + 1,
                is_owner=False,
                end_date=None,
            )
            logger.info(
                "trid= %s New split created (NOT OWNER) id= %s "
                % (self.id, new_split.id)
            )
        # archive old split
        split = old_split
        split.status = RoyaltySplit.STATUS_ARCHIVED
        split.end_date = timezone.now() - timezone.timedelta(days=1)
        split.save()
        logger.info("trid= %s Old split archived id= %s " % (self.id, old_split.id))

    def update_releases_to_new_user(self, artist_id):
        releases = ReleaseArtistRole.objects.values_list('release', flat=True).filter(
            artist=artist_id, role=ReleaseArtistRole.ROLE_PRIMARY_ARTIST
        )
        Release.objects.filter(id__in=releases).update(user=self.new_user)

    @transaction.atomic
    def execute_move_artists(self):
        logger.info(
            "trid= %s moving artists= %s to new user= %s"
            % (self.id, self.artists_list, self.new_user_id)
        )
        artist_old_user_map = self.get_artist_old_user_map()
        self.update_artist_v2_to_new_user()
        logger.info("trid= %s Updating ArtistV2 owner DONE " % self.id)
        for artist_id, old_user in artist_old_user_map.items():
            self.change_old_user_to_admin(user=old_user, artist_id=artist_id)
            logger.info(
                "trid= %s Changing old user to ADMIN user= %s artist=%s DONE"
                % (self.id, old_user, artist_id)
            )
            self.add_new_user_as_owner(artist_id)
            logger.info(
                "trid= %s Add new user as OWNER user= %s artist=%s DONE"
                % (self.id, self.new_user, artist_id)
            )
            self.update_releases_to_new_user(artist_id)
            logger.info(
                "trid= %s Updating Release for user= %s DONE" % (self.id, old_user)
            )
            splits_for_update = self.get_splits_for_update(artist_id)
            for old_split in splits_for_update:
                self.update_split(old_split, self.new_user, old_user)
