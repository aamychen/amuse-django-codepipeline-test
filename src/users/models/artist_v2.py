import logging

from django.db import models

from amuse.db.decorators import with_history
from users.models.exceptions import ArtistsDoNotExistError


logger = logging.getLogger(__name__)


@with_history
class ArtistV2(models.Model):
    name = models.CharField(db_index=True, max_length=255)
    owner = models.ForeignKey('User', on_delete=models.CASCADE, null=True, blank=True)
    image = models.CharField(max_length=512, blank=True, null=True, default=None)
    spotify_page = models.CharField(max_length=255, null=True, blank=True)
    spotify_image = models.CharField(
        max_length=512, blank=True, null=True, default=None
    )
    twitter_name = models.CharField(max_length=255, null=True, blank=True)
    facebook_page = models.CharField(max_length=255, null=True, blank=True)
    instagram_name = models.CharField(max_length=255, null=True, blank=True)
    tiktok_name = models.CharField(max_length=255, null=True, blank=True)
    soundcloud_page = models.CharField(max_length=255, null=True, blank=True)
    youtube_channel = models.CharField(max_length=255, null=True, blank=True)
    apple_id = models.CharField(max_length=120, blank=True, null=True)
    spotify_id = models.CharField(db_index=True, max_length=120, blank=True, null=True)
    spotify_for_artists_url = models.CharField(max_length=255, blank=True, null=True)
    audiomack_id = models.CharField(max_length=120, null=True, blank=True)
    audiomack_access_token = models.CharField(max_length=128, null=True, blank=True)
    audiomack_access_token_secret = models.CharField(
        max_length=128, null=True, blank=True
    )
    is_auto_generated = models.BooleanField(blank=True, null=True, editable=False)
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)
    users = models.ManyToManyField(
        'User', through='UserArtistRole', related_name='artists'
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.__original_name = self.name

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)

        if self.__original_name != self.name:
            logger.info(
                'Artist name changed from %s to %s', self.__original_name, self.name
            )

            self.__original_name = self.name

    @classmethod
    def get_artists_by_ids(cls, artists_ids):
        artists = cls.objects.filter(id__in=artists_ids)
        if not artists:
            raise ArtistsDoNotExistError('Artists were not found.')
        else:
            return artists

    def __repr__(self):
        return '<{} #{} name={}>'.format(self.__class__.__name__, self.pk, self.name)

    def __str__(self):
        return self.name

    @property
    def has_owner(self):
        if self.owner is not None:
            return True
        else:
            return False

    def is_accessible_by_admin_roles(self, user_id):
        return self.is_accessible_by(
            user_id,
            [UserArtistRole.ADMIN, UserArtistRole.OWNER, UserArtistRole.SUPERADMIN],
        )

    def is_accessible_by(self, user_id, allowed_role_types):
        if user_id == self.owner_id:
            return True
        return UserArtistRole.objects.filter(
            artist=self, type__in=allowed_role_types, user_id=user_id
        ).exists()


class UserArtistRole(models.Model):
    ADMIN = 1
    MEMBER = 2
    OWNER = 3
    SPECTATOR = 4
    SUPERADMIN = 5
    TYPE_CHOICES = (
        (ADMIN, 'admin'),
        (MEMBER, 'member'),
        (OWNER, 'owner'),
        (SPECTATOR, 'spectator'),
        (SUPERADMIN, 'superadmin'),
    )

    @staticmethod
    def get_name(role_id):
        return dict(UserArtistRole.TYPE_CHOICES)[role_id]

    user = models.ForeignKey('User', on_delete=models.CASCADE)
    artist = models.ForeignKey('ArtistV2', on_delete=models.CASCADE)
    type = models.PositiveSmallIntegerField(default=ADMIN, choices=TYPE_CHOICES)
    main_artist_profile = models.BooleanField(default=False, blank=True, null=True)
    created = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'artist')

    def __repr__(self):
        return '<{} user_id={}, artist_id={}, type={}>'.format(
            self.__class__.__name__,
            self.user_id,
            self.artist_id,
            self.get_type_display(),
        )

    def __str__(self):
        return '{}/{}'.format(self.artist, self.user)
