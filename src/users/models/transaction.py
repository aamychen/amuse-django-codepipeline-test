from decimal import Decimal
from os.path import splitext
from uuid import uuid4
from django.db import connection, models
from django.conf import settings
from amuse.storages import S3Storage
from releases.models import Store

ZERO = Decimal('0.000000000000')


def transaction_file_upload_path(instance, filename):
    return '%d-%s-%s%s' % (
        instance.type,
        str(instance.date),
        str(uuid4()),
        splitext(instance.file.name)[1],
    )


class TransactionSource(models.Model):
    name = models.CharField(max_length=120, unique=True)
    store = models.ForeignKey(Store, null=True, blank=True, on_delete=models.PROTECT)

    def __str__(self):
        return self.name


class Transaction(models.Model):
    STATUS_PENDING = 1
    STATUS_COMPLETED = 2

    STATUS_CHOICES = ((STATUS_PENDING, 'pending'), (STATUS_COMPLETED, 'completed'))

    TYPE_DEPOSIT = 1
    TYPE_WITHDRAWAL = 2

    TYPE_CHOICES = ((TYPE_DEPOSIT, 'deposit'), (TYPE_WITHDRAWAL, 'withdrawal'))

    status = models.SmallIntegerField(choices=STATUS_CHOICES, null=False, blank=False)
    type = models.SmallIntegerField(choices=TYPE_CHOICES, null=False, blank=False)

    amount = models.DecimalField(
        null=False,
        blank=False,
        max_digits=22,
        decimal_places=12,
        default=Decimal('0.0'),
        help_text='Remember to prefix with minus sign (-) when manually creating a withdrawal transaction.',
    )

    date = models.DateField()

    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    source = models.ForeignKey(
        TransactionSource, null=True, blank=True, on_delete=models.CASCADE
    )
    user = models.ForeignKey(
        'users.User',
        null=True,
        blank=True,
        related_name='transactions',
        on_delete=models.PROTECT,
    )

    # Only applicable to withdrawals
    licensed = models.BooleanField(default=False, null=True)

    class Meta:
        unique_together = ('date', 'source', 'user')
        ordering = ('date',)

    def __repr__(self):
        return f"<{self.__class__.__name__} #{self.pk} status={self.get_status_display()} type={self.get_type_display()} amount={self.amount} date={self.date} licensed={self.licensed} created={self.created} updated={self.updated} source={self.source} user={self.user}>"


class TransactionDeposit(models.Model):
    amount = models.DecimalField(
        null=False,
        blank=False,
        max_digits=22,
        decimal_places=12,
        default=Decimal('0.0'),
    )
    transaction = models.ForeignKey(
        Transaction, related_name='deposits', on_delete=models.CASCADE
    )
    isrc = models.ForeignKey('codes.ISRC', on_delete=models.CASCADE)

    def __repr__(self):
        return f"<{self.__class__.__name__} #{self.pk} amount={self.amount} isrc={self.isrc}>"

    class Meta:
        unique_together = ('transaction', 'isrc')


class TransactionWithdrawal(models.Model):
    PAYEE_TYPES = [('person', 'Person'), ('company', 'Company')]

    payee_type = models.TextField(choices=PAYEE_TYPES, null=True, blank=True)

    identification_number = models.TextField(null=True, blank=True)
    name = models.CharField(max_length=120, null=False)
    address = models.TextField(null=True, blank=True)
    country = models.CharField(max_length=2, null=False)
    email = models.CharField(max_length=120, null=True)
    phone = models.CharField(max_length=120, null=True)
    hyperwallet_payment_token = models.CharField(max_length=50, null=True, blank=True)

    verified = models.BooleanField(default=False, null=True)
    transaction = models.OneToOneField(
        Transaction,
        primary_key=True,
        related_name='withdrawal',
        on_delete=models.CASCADE,
    )


class TransactionFile(models.Model):
    STATUS_PENDING = 1
    STATUS_COMPLETED = 2
    STATUS_FAILED = 3

    STATUS_CHOICES = (
        (STATUS_PENDING, 'Pending'),
        (STATUS_COMPLETED, 'Completed'),
        (STATUS_FAILED, 'Failed'),
    )

    TYPE_FUGA = 1

    TYPE_CHOICES = ((TYPE_FUGA, 'Fuga'),)

    status = models.SmallIntegerField(
        default=STATUS_PENDING, choices=STATUS_CHOICES, null=False
    )
    type = models.SmallIntegerField(choices=TYPE_CHOICES, null=False)
    date = models.DateField(
        null=False, help_text='Date to user for transaction deposit date.'
    )
    file = models.FileField(
        storage=S3Storage(bucket_name=settings.AWS_TRANSACTION_FILE_BUCKET_NAME),
        upload_to=transaction_file_upload_path,
    )


def fetch_user_transactions_v2(user):
    return (
        user.transactions.all()
        .select_related('source')
        .prefetch_related('deposits', 'deposits__isrc', 'deposits__isrc__song_set')
    )


def fetch_user_transactions_v3(user):
    with connection.cursor() as c:
        c.callproc('user_transactions_v3', [user.id])
        results = c.fetchone()[0]
        return results or {"balance": ZERO, "total": ZERO}


def user_balance_all(user):
    return Decimal(
        Transaction.objects.filter(user=user).aggregate(
            balance=models.Sum(models.F('amount'))
        )['balance']
        or ZERO
    )


def user_balance_unlicensed(user):
    deposited = Decimal(
        TransactionDeposit.objects.filter(
            transaction__user=user, isrc__licensed=False
        ).aggregate(amount=models.Sum(models.F('amount')))['amount']
        or ZERO
    )

    withdrawn = Decimal(
        Transaction.objects.filter(
            user=user, type=Transaction.TYPE_WITHDRAWAL, licensed=False
        ).aggregate(amount=models.Sum(models.F('amount')))['amount']
        or ZERO
    )

    return deposited + withdrawn
