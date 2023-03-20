from datetime import date
from django.db import models
from users.models.user import User
from .transaction import Transaction


class LegacyRoyaltyAdvance(models.Model):
    STATUS_CREATED = 0
    STATUS_ACTIVE = 1
    STATUS_SUBMITTED = 2
    STATUS_CANCELLED = 3

    STATUS_CHOICES = {
        STATUS_CREATED: 'created',
        STATUS_ACTIVE: 'active',
        STATUS_SUBMITTED: 'submitted',
        STATUS_CANCELLED: 'cancelled',
    }

    status = models.PositiveSmallIntegerField(
        default=STATUS_CREATED, choices=[(k, v) for k, v in STATUS_CHOICES.items()]
    )

    advance_amount = models.DecimalField(max_digits=22, decimal_places=2)
    commission_amount = models.DecimalField(max_digits=22, decimal_places=2)
    commission_rate = models.DecimalField(max_digits=11, decimal_places=10)

    date_start = models.DateField()
    date_end = models.DateField()

    label = models.CharField(max_length=256)

    full_name = models.CharField(max_length=256, blank=True, null=True)
    address = models.CharField(max_length=512, blank=True, null=True)
    country = models.CharField(max_length=2, blank=True, null=True)
    email = models.EmailField(max_length=256, blank=True, null=True)
    identification_number = models.CharField(max_length=32, blank=True, null=True)

    date_created = models.DateTimeField(auto_now_add=True)
    date_updated = models.DateTimeField(auto_now=True)

    user = models.ForeignKey(
        User, related_name='legacy_royalty_advances', on_delete=models.CASCADE
    )

    transactions = models.ManyToManyField(Transaction)

    def __repr__(self):
        return '<{} #{} user_id={} status={} advance_amount={} commision_amount={} commission_rate={} date_start={} date_end={}>'.format(
            self.__class__.__name__,
            self.id,
            self.user_id,
            self.get_status_display(),
            self.advance_amount,
            self.commission_amount,
            self.commission_rate,
            self.date_start,
            self.date_end,
        )

    def save(self, *args, **kwargs):
        raise DeprecationWarning()
