from bitfield import BitField
from django.conf import settings
from django.db import models

from amuse.db.decorators import with_history
from amuse.storages import S3Storage
from codes.models import ISRC
from releases.models import Genre, MetadataLanguage, Release
from releases.models.exceptions import (
    ArtistsIDsDoNotExistError,
    SongsIDsDoNotExistError,
)
from users.models import User


@with_history
class Song(models.Model):
    DISCLAIMER_FLAGS = (
        ('DIST', 'Not distributed before'),
        ('SAMPLE', 'Does not contain samples'),
        ('COVER', 'Is not a cover'),
        ('COMPOSER', 'Sole composer'),
    )

    EXPLICIT_FALSE = 0
    EXPLICIT_TRUE = 1
    EXPLICIT_CLEAN = 2

    EXPLICIT_CHOICES = (
        (EXPLICIT_FALSE, 'none'),
        (EXPLICIT_TRUE, 'explicit'),
        (EXPLICIT_CLEAN, 'clean'),
    )

    ORIGIN_ORIGINAL = 1
    ORIGIN_COVER = 2
    ORIGIN_REMIX = 3
    ORIGIN_CHOICES = (
        (ORIGIN_ORIGINAL, 'original'),
        (ORIGIN_COVER, 'cover'),
        (ORIGIN_REMIX, 'remix'),
    )

    YT_CONTENT_ID_NONE = 0
    YT_CONTENT_ID_BLOCK = 1
    YT_CONTENT_ID_MONETIZE = 2
    YT_CONTENT_ID_CHOICES = (
        (YT_CONTENT_ID_NONE, 'none'),
        (YT_CONTENT_ID_BLOCK, 'block'),
        (YT_CONTENT_ID_MONETIZE, 'monetize'),
    )

    ERROR_FLAGS = (
        ('rights_samplings', 'Contains samplings'),
        ('rights_remix', 'Remix'),
        ('rights_no-rights', 'No rights'),
        ('audio_bad-quality', 'Audio: Bad quality'),
        ('explicit_lyrics', 'Explicit: Lyrics'),
        ('genre_not-approved', 'Not approved genre'),
        ('audio_too-short', 'Audio: Too short'),
        ("wrong-isrc", "ISRC Issue"),
        ("misleading-artist-name", "Misleadning artist name"),
        ("audio_silent-end-beginning", "Audio: Silent end/beginning"),
        ("audio_cut-short", "Audio: Cut Short"),
        ("audio_continuous-mix", "Audio: Continuous Mix"),
    )

    ERROR_FLAGS_MAP = {error_key: error_text for error_key, error_text in ERROR_FLAGS}

    sequence = models.SmallIntegerField(db_index=True)

    name = models.CharField(max_length=255, blank=False, null=False)
    version = models.CharField(max_length=255, blank=True, null=True, default=None)

    recording_year = models.SmallIntegerField(blank=False, null=False)
    recording_place_id = models.CharField(
        max_length=120, blank=True, null=True, default=None
    )
    original_release_date = models.DateField(blank=True, null=True)

    explicit = models.PositiveSmallIntegerField(
        default=EXPLICIT_FALSE, choices=EXPLICIT_CHOICES
    )
    origin = models.PositiveSmallIntegerField(
        default=ORIGIN_ORIGINAL, choices=ORIGIN_CHOICES
    )

    filename = models.CharField(max_length=255, blank=True, default='')

    isrc = models.ForeignKey(ISRC, on_delete=models.CASCADE, null=True, blank=True)
    genre = models.ForeignKey(Genre, on_delete=models.PROTECT, related_name='songs')
    release = models.ForeignKey(Release, related_name='songs', on_delete=models.CASCADE)

    meta_language = models.ForeignKey(
        MetadataLanguage, null=True, blank=True, on_delete=models.CASCADE
    )
    meta_audio_locale = models.ForeignKey(
        MetadataLanguage,
        null=True,
        blank=True,
        related_name='audio_locale',
        on_delete=models.CASCADE,
    )
    cover_licensor = models.TextField(blank=True)
    youtube_content_id = models.PositiveSmallIntegerField(
        default=YT_CONTENT_ID_NONE, choices=YT_CONTENT_ID_CHOICES
    )

    error_flags = BitField(default=None, null=True, flags=ERROR_FLAGS)
    artists = models.ManyToManyField('users.ArtistV2', through='SongArtistRole')
    preview_start_time = models.SmallIntegerField(null=True, blank=True)

    def __str__(self):
        return self.name

    @property
    def meta_flags_dict(self):
        return {
            'cover': self.origin == self.ORIGIN_COVER,
            'explicit': self.explicit == self.EXPLICIT_TRUE,
            'remix': self.origin == self.ORIGIN_REMIX,
        }

    @property
    def isrc_code(self):
        if self.isrc is not None:
            return self.isrc.code

    def get_primary_artists(self):
        primary_artist_ids = [
            artist_role['artist_id']
            for artist_role in self.artists_roles
            if 'primary_artist' in artist_role['roles']
        ]
        return self.artists.filter(pk__in=primary_artist_ids).distinct()

    @property
    def artists_invites(self):
        artists_invites_list = []

        song_artist_invites_list = self.song_invitations.all()
        for invite in song_artist_invites_list:
            artists_invites_list.append(
                {
                    'artist_id': invite.artist.id,
                    'artist_name': invite.artist.name,
                    'status': invite.status,
                }
            )
        return artists_invites_list

    @property
    def artists_roles(self):
        song_artist_roles_list = self.songartistrole_set.all()

        grouped = dict()
        for sar in song_artist_roles_list:
            artist_id = sar.artist_id
            if sar.artist_id not in grouped:
                grouped[artist_id] = {'artist_id': artist_id, 'roles': []}

            grouped[artist_id]['roles'].append(sar.get_role_display())

        return list(grouped.values())

    def get_next_royalty_split_revision(self):
        """
        Get the revision of the last royalty_split and return the next id.

        It will return the current royalty split revision plus 1 if there are
        already royalty splits otherwise 1.
        """
        last_royalty_split = self.royalty_splits.order_by('revision').last()
        if last_royalty_split:
            revision = last_royalty_split.revision + 1
        else:
            revision = 1

        return revision

    def has_locked_splits(self):
        return self.royalty_splits.filter(is_locked=True).exists()

    class Meta:
        ordering = ['sequence']

    def save(self, *args, **kwargs):
        if self.release.status == Release.STATUS_APPROVED and self.isrc is None:
            self.isrc = ISRC.objects.use(None)
        super().save(*args, **kwargs)


@with_history
class SongFileUpload(models.Model):
    STATUS_CREATED = 0
    STATUS_COMPLETED = 1

    STATUS_CHOICES = ((STATUS_CREATED, 'Created'), (STATUS_COMPLETED, 'Completed'))

    filename = models.CharField(max_length=64, null=True, db_index=True)
    status = models.PositiveSmallIntegerField(
        default=STATUS_CREATED, choices=STATUS_CHOICES
    )

    link = models.TextField(null=True, default=None)
    transcode_id = models.CharField(max_length=255, null=True, db_index=True)

    user = models.ForeignKey(User, null=False, on_delete=models.CASCADE)
    song = models.OneToOneField(
        Song, null=True, related_name='upload', on_delete=models.CASCADE
    )


@with_history
class SongFile(models.Model):
    TYPE_FLAC = 1
    TYPE_MP3 = 2

    TYPE_CHOICES = ((TYPE_FLAC, 'FLAC'), (TYPE_MP3, 'MP3'))

    type = models.SmallIntegerField(choices=TYPE_CHOICES)

    duration = models.PositiveSmallIntegerField(null=False)

    song = models.ForeignKey(Song, related_name='files', on_delete=models.CASCADE)
    file = models.FileField(
        storage=S3Storage(bucket_name=settings.AWS_SONG_FILE_TRANSCODED_BUCKET_NAME)
    )
    checksum = models.TextField(null=True, blank=True, editable=False)

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)

        if not self.checksum:
            from amuse.tasks import save_song_file_checksum

            if self.file:
                save_song_file_checksum.delay(self.id)


class SongArtistRole(models.Model):
    ROLE_PRIMARY_ARTIST = 1
    ROLE_FEATURED_ARTIST = 2
    ROLE_WRITER = 3
    ROLE_PRODUCER = 4
    ROLE_MIXER = 5
    ROLE_REMIXER = 6

    ROLE_CHOICES = (
        (ROLE_PRIMARY_ARTIST, 'primary_artist'),
        (ROLE_FEATURED_ARTIST, 'featured_artist'),
        (ROLE_WRITER, 'writer'),
        (ROLE_PRODUCER, 'producer'),
        (ROLE_MIXER, 'mixer'),
        (ROLE_REMIXER, 'remixer'),
    )

    artist = models.ForeignKey('users.ArtistV2', on_delete=models.SET_NULL, null=True)
    song = models.ForeignKey('Song', on_delete=models.DO_NOTHING)
    role = models.SmallIntegerField(choices=ROLE_CHOICES)
    created = models.DateTimeField(auto_now_add=True)
    artist_sequence = models.SmallIntegerField(blank=False, null=True)

    class Meta:
        ordering = ['id']
        unique_together = ('artist', 'song', 'role')

    @staticmethod
    def get_role_for_keyword(keyword):
        """
        Using the keyword for Contributor role on a song, return the Song Role
        """
        if not keyword:
            raise ValueError("No song artist role can be defined due to empty keyword")
        for role in SongArtistRole.ROLE_CHOICES:
            if role[1] == keyword:
                return role[0]
        raise ValueError("Song Artist Role for keyword %s not found" % keyword)

    @classmethod
    def get_songs_ids_by_artist_id(cls, artist_id):
        """
        Get all songs' IDs filtered by artist_id.

        Args:
        ----
            artist_id (int): The artist ID we will filter by.

        Returns:
        -------
            songs_ids (QuerySet): All songs' IDs as queryset which have the
                same artist ID as artist_id.

        Raises:
        ------
            SongsIDsDoNotExistError will be raised when songs_ids is an
                EmptyQuerySet which means there are no songs connected to the
                artist.
        """
        songs_artist_roles = cls.objects.filter(artist_id=artist_id)

        songs_ids = songs_artist_roles.values_list('song_id', flat=True)

        if not songs_ids:
            raise SongsIDsDoNotExistError('Artist does not have any songs.')
        else:
            return songs_ids

    @classmethod
    def get_artists_ids_by_songs_ids(cls, artist_id, songs_ids):
        """
        Get all songs' IDs filtered by songs_ids and excluding artist_id and
        artists with a writer role only.

        We need to get all the artits IDs of the artists which contributed with
        a specific artist based on specific songs.

        Args:
        ----
            artist_id (int): The artist ID we will exclude.
            songs_ids (QuerySet): The songs IDs we will filter by.

        Returns:
        -------
            artists_ids (QuerySet): All artists' IDs as queryset which share
                the given songs with given artist excluding himself.

        Raises:
        ------
            ArtistsIDsDoNotExistError will be raised when artists_ids is an
                EmptyQuerySet which means no artists have ever contributed with
                the given artist on the given songs.
        """
        songs_artist_roles = (
            cls.objects.filter(song_id__in=songs_ids)
            .exclude(artist_id=artist_id)
            .exclude(role=cls.ROLE_WRITER)
            .distinct()
        )

        artists_ids = songs_artist_roles.values_list('artist_id', flat=True)
        if not artists_ids:
            raise ArtistsIDsDoNotExistError(
                'Artists does not have any previously contributed artists.'
            )
        else:
            return artists_ids
