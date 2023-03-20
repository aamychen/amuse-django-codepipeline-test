from django.db import models

from releases.managers import RoyaltySplitManager
from releases.models import Song
from users.models import User
from users.models.royalty_invitation import RoyaltyInvitation


class RoyaltySplit(models.Model):
    STATUS_PENDING = 0
    STATUS_ACTIVE = 1
    STATUS_CANCELED = 2  # DON'T USE. WILL BE REMOVED
    STATUS_ARCHIVED = 3
    STATUS_CONFIRMED = 4

    STATUS_CHOICES = (
        (STATUS_PENDING, 'pending'),
        (STATUS_ACTIVE, 'active'),
        (STATUS_ARCHIVED, 'archived'),
        (STATUS_CONFIRMED, 'confirmed'),
    )

    # User-payee (normally the artist's owner)
    user = models.ForeignKey(User, null=True, on_delete=models.DO_NOTHING)
    song = models.ForeignKey(
        Song, null=False, related_name="royalty_splits", on_delete=models.CASCADE
    )
    rate = models.DecimalField(
        max_digits=5, decimal_places=4, help_text='A value from 0.0000 to 1.0000'
    )
    created = models.DateTimeField(auto_now_add=True)
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    status = models.PositiveSmallIntegerField(
        default=STATUS_PENDING, choices=STATUS_CHOICES
    )
    revision = models.PositiveIntegerField(default=1)
    is_owner = models.BooleanField(default=False)
    is_locked = models.BooleanField(default=False)

    objects = RoyaltySplitManager()

    def save(self, *args, **kwargs):
        if self.pk is None:
            self.is_owner = self._get_is_owner()
        return super().save(*args, **kwargs)

    def get_user_name(self):
        """
        Returns the name of the user that belongs to the royalty_split or
        returns the name from the RoyaltyInvitation.

        Returns:
        -------
            user_name (str): The user name extracted from the user that belongs to
                the royalty split and in case a royalty split doesn't have a user,
                the name is gonna be extracted from RoyaltyInvitation which as the
                same RoyaltySplit when created.
        """
        if self.user is not None:
            user_name = self.user.name
        else:
            royalty_invitation = RoyaltyInvitation.objects.get(royalty_split=self)
            user_name = royalty_invitation.name

        return user_name

    def get_user_profile_photo_url(self):
        """
        Gets the user profile's photo full URL.

        Returns:
        -------
            photo_url (str or None): In case the royalty split doesn't has user
                None will be returned, otherwise it will return whatever the
                self.user.profile_photo returns.
        """
        if self.user is not None:
            return self.user.profile_photo
        else:
            return None

    def _get_is_owner(self):
        '''User owning main_primary_artist for this track's Release'''
        main_primary_artist = self.song.release.main_primary_artist
        if main_primary_artist:
            artist_owner = main_primary_artist.owner
            if artist_owner:
                owner_id = artist_owner.pk
                return self.user_id == owner_id

        return False
