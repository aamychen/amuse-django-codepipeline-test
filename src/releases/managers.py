import logging
from datetime import timedelta

from django.db import models
from django.db.models import F, Q, OuterRef, Subquery
from django.utils import timezone

from subscriptions.models import Subscription


logger = logging.getLogger(__name__)


class ReleaseManager(models.Manager):
    def pro(self):
        '''Filter releases created by pro user'''
        date = timezone.now().date()
        return (
            self.get_queryset()
            .filter(created_by__subscriptions__valid_from__lte=date)
            .filter(self._subscription_valid_until_query(date))
        )

    def non_pro(self):
        '''Filter releases not created by pro user'''
        date = timezone.now().date()
        return self.get_queryset().filter(
            ~Q(
                Q(created_by__subscriptions__valid_from__lte=date)
                & (self._subscription_valid_until_query(date))
            )
        )

    def _subscription_valid_until_query(self, date):
        return (
            Q(created_by__subscriptions__status__in=Subscription.VALID_STATUSES)
            & (
                Q(created_by__subscriptions__valid_until=None)
                | Q(created_by__subscriptions__valid_until__gte=date)
            )
        ) | (
            Q(created_by__subscriptions__status=Subscription.STATUS_GRACE_PERIOD)
            & Q(created_by__subscriptions__grace_period_until__gte=date)
        )


class BaseRoyaltySplitManager(models.Manager):
    def invalid_true_owner(self):
        """
        Returns splits with is_owner=True and
        split.user_id != split.song.release.main_primary_artist.owner_id
        """
        from releases.models import ReleaseArtistRole

        artists = ReleaseArtistRole.objects.filter(
            release_id=OuterRef('song__release_id'),
            role=ReleaseArtistRole.ROLE_PRIMARY_ARTIST,
            main_primary_artist=True,
        )
        return (
            self.get_queryset()
            .select_related("song__release")
            .annotate(owner_id=Subquery(artists.values("artist__owner_id")[:1]))
            .filter(~Q(user_id=F("owner_id")), is_owner=True)
            .distinct()
        )

    def invalid_false_owner(self):
        """
        Returns splits with is_owner=False and
        split.user_id == split.song.release.main_primary_artist.owner_id
        """
        from releases.models import ReleaseArtistRole

        artists = ReleaseArtistRole.objects.filter(
            release_id=OuterRef('song__release_id'),
            role=ReleaseArtistRole.ROLE_PRIMARY_ARTIST,
            main_primary_artist=True,
        )
        return (
            self.get_queryset()
            .annotate(owner_id=Subquery(artists.values("artist__owner_id")[:1]))
            .filter(user_id=F("owner_id"), is_owner=False, user__isnull=False)
            .distinct()
        )


class RoyaltySplitDifferentRevisionsError(Exception):
    """
    Raised when all splits in a queryset does not belong to the same revision.
    """


# TODO Add logging with split ids and song id
class RoyaltySplitQueryset(models.QuerySet):
    def activate(self, new_revision=None):
        """
        When invite splits are created they will get an initial status of PENDING.
        Once all splits in the new revision have a status of CONFIRMED, we will run
        this method that updates the status of all splits in the new revision to
        ACTIVE.

        This method works with first revision splits as well as the update() functions
        does not raise any errors on empty querysets.
        """
        if not self._are_same_revision():
            raise RoyaltySplitDifferentRevisionsError()

        new_revision = new_revision if new_revision else self[0].revision

        start_date = None if new_revision == 1 else timezone.now().today()

        logger.info(
            "Activated splits for song_id %s and revision %s with start_date %s"
            % (self[0].song_id, new_revision, start_date)
        )

        return self.update(
            revision=new_revision,
            status=self.model.STATUS_ACTIVE,
            start_date=start_date,
        )

    def archive(self):
        """
        When splits are updated we change the status of the previous ACTIVE splits to
        ARCHIVED.
        """
        if not self._are_same_revision():
            raise RoyaltySplitDifferentRevisionsError()

        yesterday = timezone.now().today() - timedelta(days=1)

        logger.info(
            "Archived splits for song_id %s and revision %s with end_date %s"
            % (self[0].song_id, self[0].revision, yesterday)
        )

        return self.update(status=self.model.STATUS_ARCHIVED, end_date=yesterday)

    def revision_is_confirmed(self):
        """
        Helper to check if all splits in a revision have the status CONFIRMED and can
        thus be activated (all splits in the revision gets status ACTIVE)
        """
        if not self._are_same_revision():
            raise RoyaltySplitDifferentRevisionsError()

        return all([split.status == self.model.STATUS_CONFIRMED for split in self])

    def revision_is_inactive(self):
        """
        Helper to check if a revision is inactive
        """
        if not self._are_same_revision():
            raise RoyaltySplitDifferentRevisionsError()

        return any([split.status == self.model.STATUS_PENDING for split in self])

    def last_revision(self, song_id):
        """
        Get last revision splits for song_id
        """
        return self.filter(
            song_id=song_id,
            revision=Subquery(
                self.filter(song_id=song_id)
                .order_by("-revision")
                .values("revision")[:1]
            ),
        )

    def _are_same_revision(self):
        return all(
            [
                split.revision == self[0].revision and split.song == self[0].song
                for split in self
            ]
        )


RoyaltySplitManager = BaseRoyaltySplitManager.from_queryset(RoyaltySplitQueryset)
