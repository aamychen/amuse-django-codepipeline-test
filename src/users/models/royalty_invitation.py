from django.db import models
from django.utils import timezone
from datetime import timedelta


class RoyaltyInvitation(models.Model):
    EXPIRATION_DAYS = 30
    MIN_RESEND_DAYS = 3

    STATUS_CREATED = 1
    STATUS_PENDING = 2
    STATUS_ACCEPTED = 3
    STATUS_DECLINED = 4

    STATUS_CHOICES = (
        (STATUS_CREATED, 'created'),
        (STATUS_PENDING, 'pending'),
        (STATUS_ACCEPTED, 'accepted'),
        (STATUS_DECLINED, 'declined'),
    )

    inviter = models.ForeignKey(
        'users.User',
        on_delete=models.DO_NOTHING,
        related_name='royalty_invitations_sent',
    )
    invitee = models.ForeignKey(
        'users.User',
        on_delete=models.DO_NOTHING,
        related_name='royalty_invitations_received',
        blank=True,
        null=True,
    )
    royalty_split = models.ForeignKey('releases.RoyaltySplit', on_delete=models.CASCADE)
    status = models.PositiveSmallIntegerField(
        choices=STATUS_CHOICES, default=STATUS_CREATED
    )
    email = models.EmailField(max_length=120, null=True)
    phone_number = models.CharField(max_length=20, null=True)
    name = models.CharField(max_length=120)
    token = models.CharField(max_length=512, unique=True, null=True)

    last_sent = models.DateTimeField(null=True)
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    @property
    def expiration_time(self):
        if self.last_sent is None:
            return timezone.now() + timedelta(days=self.EXPIRATION_DAYS)

        return self.last_sent + timedelta(days=self.EXPIRATION_DAYS)

    @property
    def valid(self):
        valid_status = self.status == self.STATUS_PENDING
        expired = self.last_sent is None or timezone.now() > self.expiration_time
        return valid_status and not expired
