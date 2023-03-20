from django.db import models
from django.utils import timezone


class SongArtistInvitation(models.Model):
    EXPIRATION_DAYS = 30
    MIN_RESEND_DAYS = 3

    STATUS_CREATED = 1
    STATUS_PENDING = 2
    STATUS_ACCEPTED = 3
    STATUS_DECLINED = 4

    STATUS_CHOICES = (
        (STATUS_PENDING, 'pending'),
        (STATUS_ACCEPTED, 'accepted'),
        (STATUS_DECLINED, 'declined'),
    )

    inviter = models.ForeignKey(
        'users.User', on_delete=models.DO_NOTHING, related_name='song_invitations_sent'
    )
    invitee = models.ForeignKey(
        'users.User',
        on_delete=models.DO_NOTHING,
        related_name='song_invitations_accepted',
        blank=True,
        null=True,
    )
    artist = models.ForeignKey('users.ArtistV2', on_delete=models.DO_NOTHING)
    song = models.ForeignKey(
        'releases.Song', on_delete=models.CASCADE, related_name='song_invitations'
    )
    email = models.EmailField(max_length=120)
    phone_number = models.CharField(max_length=20, blank=True, null=True)
    token = models.CharField(max_length=512, unique=True)
    status = models.PositiveSmallIntegerField(
        choices=STATUS_CHOICES, default=STATUS_PENDING
    )
    last_sent = models.DateTimeField(auto_now_add=True)

    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    @property
    def valid(self):
        pending = self.status == self.STATUS_PENDING
        expired = (timezone.now() - self.last_sent).days > self.EXPIRATION_DAYS
        return pending and not expired
