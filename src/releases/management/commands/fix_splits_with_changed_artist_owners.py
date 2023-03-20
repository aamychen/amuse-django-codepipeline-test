from copy import copy
from datetime import date, timedelta

from django.contrib.admin.models import LogEntry, CHANGE
from django.contrib.contenttypes.models import ContentType
from django.core.management.base import BaseCommand
from django.db.models import Count

from releases.models import ReleaseArtistRole, Song, RoyaltySplit, Release
from users.models import ArtistV2


SPLIT_STATUS_LIST = (RoyaltySplit.STATUS_ACTIVE,)


class Command(BaseCommand):
    help = """Fixes splits for manually changed artist owners"""

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            dest='is_dry_run',
            action='store_true',
            help='Just print, do not update',
            default=False,
        )
        parser.add_argument(
            '--fix-releases',
            nargs='+',
            type=int,
            help='Single/multiple release_ids separated by space. Example: 1 2 3 4',
        )
        parser.add_argument('--limit', dest='limit', type=int)

    def handle(self, *args, **kwargs):
        is_dry_run = kwargs['is_dry_run']
        fix_releases = kwargs['fix_releases']
        limit = kwargs.get('limit')

        if is_dry_run:
            self.stdout.write("Start Dry")
        else:
            self.stdout.write("Start Real Run")

        if fix_releases:
            self._fix_releases(fix_releases, is_dry_run)
            return

        artist_entries = self._get_artist_log_entries()
        artist_ids = artist_entries.values_list("object_id", flat=True)

        # Filter out and log artists that have changed owners multiple times
        # as we only update one owner change back in history as multi step is
        # much more complex
        artists = ArtistV2.objects.filter(id__in=list(artist_ids))

        artists_to_fix = []

        for artist in artists:
            # Get all unique owners that were previously owners of this artist
            previous_owners = self._get_previous_owners_from_artist_history(artist)
            previous_owners_count = len(previous_owners)

            if previous_owners_count > 1:
                self.stdout.write(
                    "%s needs to be fixed manually as it has %s owner changes"
                    % (artist.id, previous_owners_count)
                )
                continue
            else:
                previous_owner = previous_owners.first()

            current_owner_id = artist.owner_id
            current_owner = artist.history.filter(owner_id=current_owner_id).first()

            if current_owner and previous_owner:
                change_date = current_owner.updated
                previous_owner_id = previous_owner.owner_id

                artists_to_fix.append(
                    {
                        "artist": artist,
                        "current_owner_id": current_owner_id,
                        "previous_owner_id": previous_owner_id,
                        "change_date": change_date,
                    }
                )

        self.stdout.write("Found %s changed artists to process" % len(artists_to_fix))

        if limit:
            self.stdout.write("Limit processing to %s artists" % limit)
            artists_to_fix = artists_to_fix[:limit]

        # Loop over artists with owner changes to fix their splits
        for artist in artists_to_fix:
            release_ids = ReleaseArtistRole.objects.filter(
                artist_id=artist["artist"].id, main_primary_artist=True
            ).values_list("release_id", flat=True)

            song_ids = Song.objects.filter(release_id__in=release_ids).values_list(
                "id", flat=True
            )

            self._process_splits_for_songs(song_ids, artist, is_dry_run)

        if is_dry_run:
            self.stdout.write("Finished Dry Run")
        else:
            self.stdout.write("Finished Real Run")

    def _archive_previous_revision(self, artist, last_revision_splits, is_dry_run):
        archived_splits_end_date = artist["change_date"] - timedelta(days=1)

        kwargs = {
            "status": RoyaltySplit.STATUS_ARCHIVED,
            "end_date": archived_splits_end_date,
        }

        last_revision_owner_split = last_revision_splits.get(
            user_id=artist["previous_owner_id"]
        )

        if not is_dry_run:
            last_revision_owner_split.is_owner = True
            last_revision_owner_split.save()

            last_revision_splits.update(**kwargs)

        self.stdout.write(
            "Archived previous revision %s for artist %s, owner %s, song %s and end_date %s"
            % (
                last_revision_splits[0].revision,
                artist["artist"].id,
                artist["previous_owner_id"],
                last_revision_splits[0].song.id,
                kwargs["end_date"],
            )
        )

        return last_revision_splits

    def _create_new_revision(self, artist, archived_splits, is_dry_run):
        new_revision = archived_splits[0].revision + 1

        if not is_dry_run:
            for archived_split in archived_splits:
                split = copy(archived_split)
                split.pk = None

                if split.user_id == artist["previous_owner_id"]:
                    split.user_id = artist["current_owner_id"]
                    split.is_owner = True

                split.status = RoyaltySplit.STATUS_ACTIVE
                split.start_date = artist["change_date"]
                split.end_date = None
                split.revision = new_revision
                split.save()

        self.stdout.write(
            "Created new revision %s for artist %s, owner %s, song %s and start_date %s"
            % (
                new_revision,
                artist["artist"].id,
                artist["current_owner_id"],
                archived_splits[0].song_id,
                artist["change_date"],
            )
        )

    def _get_artist_log_entries(self, artist_ids=None):
        # Get artists manually changed from jarvi5
        kwargs = {
            "content_type_id": ContentType.objects.get(model='artistv2').id,
            "action_flag": CHANGE,
        }

        if artist_ids:
            kwargs["object_id__in"] = artist_ids

        artist_entries = LogEntry.objects.filter(**kwargs)

        return artist_entries

    def _get_previous_owners_from_artist_history(self, artist):
        previous_owners = (
            artist.history.all()
            .exclude(owner_id=artist.owner_id)
            .order_by("owner_id", "updated")
            .distinct("owner_id")
        )

        return previous_owners

    def _process_splits_for_songs(self, song_ids, split_updates, is_dry_run):
        # This query won't pick up new splits created after an artist owner
        # change but that should be fine as is_owner is set correctly
        # dynamically or by backfill?
        if RoyaltySplit.objects.filter(song_id__in=song_ids, is_locked=True).exists():
            self.stdout.write("Can't update locked splits")
            return

        for song_id in song_ids:
            last_split = (
                RoyaltySplit.objects.filter(
                    song_id=song_id,
                    user_id=split_updates["previous_owner_id"],
                    is_owner=False,
                )
                .order_by("-revision")
                .first()
            )

            if last_split:
                if last_split.status != RoyaltySplit.STATUS_ACTIVE:
                    self.stdout.write(
                        "Skip. As last split is not active for artist %s song %s"
                        % (split_updates["artist"].id, song_id)
                    )
                    continue
            else:
                self.stdout.write(
                    "Skip. Can't find non-owner active split for artist %s song %s"
                    % (split_updates["artist"].id, song_id)
                )
                continue

            last_revision_splits = RoyaltySplit.objects.last_revision(song_id=song_id)

            archived_splits = self._archive_previous_revision(
                split_updates, last_revision_splits, is_dry_run
            )

            self._create_new_revision(split_updates, archived_splits, is_dry_run)

    def _fix_releases(self, release_ids, is_dry_run):
        self.stdout.write("Process release_ids %s" % release_ids)

        releases = Release.objects.filter(pk__in=release_ids)

        for release in releases:
            artist = release.main_primary_artist
            current_owner = artist.owner
            original_artist_owner = release.user

            if original_artist_owner == current_owner:
                self.stdout.write("Owner has not change so aborting.")
                return

            artist_entries = self._get_artist_log_entries([artist.id])

            change_date = (
                artist_entries.filter(
                    object_id=artist.id, change_message__icontains='"owner"'
                )
                .order_by("action_time")
                .first()
                .action_time
            )

            split_updates = {
                "artist": artist,
                "current_owner_id": current_owner.id,
                "previous_owner_id": original_artist_owner.id,
                "change_date": change_date,
            }
            song_ids = release.songs.all().values_list("id", flat=True)

            self._process_splits_for_songs(song_ids, split_updates, is_dry_run)
