from django.db import models
from django.utils import timezone


class TeamInvitation(models.Model):
    EXPIRATION_DAYS = 30
    MIN_RESEND_MINUTES = 3

    STATUS_PENDING = 1
    STATUS_ACCEPTED = 2
    STATUS_DECLINED = 3
    STATUS_EXPIRED = 4

    STATUS_CHOICES = (
        (STATUS_PENDING, 'pending'),
        (STATUS_ACCEPTED, 'accepted'),
        (STATUS_DECLINED, 'declined'),
        (STATUS_EXPIRED, 'expired'),
    )

    TEAM_ROLE_ADMIN = 1
    TEAM_ROLE_MEMBER = 2
    TEAM_ROLE_OWNER = 3
    TEAM_ROLE_SPECTATOR = 4
    TEAM_ROLE_CHOICES = (
        (TEAM_ROLE_ADMIN, 'admin'),
        (TEAM_ROLE_MEMBER, 'member'),
        (TEAM_ROLE_OWNER, 'owner'),
        (TEAM_ROLE_SPECTATOR, 'spectator'),
    )

    inviter = models.ForeignKey(
        'users.User', on_delete=models.DO_NOTHING, related_name='team_invitations_sent'
    )
    invitee = models.ForeignKey(
        'users.User',
        on_delete=models.DO_NOTHING,
        related_name='team_invitations_received',
        blank=True,
        null=True,
    )
    artist = models.ForeignKey('users.ArtistV2', on_delete=models.DO_NOTHING)
    email = models.EmailField(max_length=120, blank=True, null=True)
    phone_number = models.CharField(max_length=20, blank=True, null=True)
    first_name = models.CharField(max_length=255, blank=True, null=True)
    last_name = models.CharField(max_length=255, blank=True, null=True)
    token = models.CharField(max_length=512, unique=True)
    status = models.PositiveSmallIntegerField(
        choices=STATUS_CHOICES, default=STATUS_PENDING
    )
    team_role = models.PositiveSmallIntegerField(choices=TEAM_ROLE_CHOICES)
    last_sent = models.DateTimeField(auto_now_add=True)

    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    @property
    def valid(self):
        pending = self.status == self.STATUS_PENDING
        return pending

    @staticmethod
    def get_status_name(status_id):
        return dict(TeamInvitation.STATUS_CHOICES)[status_id]
