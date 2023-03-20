from decimal import Decimal
from django.db import models
from users.models import User
from countries.models import Currency, Country
from amuse.utils import parseJSONField
from django.db.models import JSONField


class Provider(models.Model):
    name = models.TextField()
    external_id = models.CharField(
        max_length=255,
        help_text="External provider identifier eg Hyperwallet program token",
    )
    active = models.BooleanField(default=True)
    created = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class Payee(models.Model):
    TYPE_INDIVIDUAL = 1
    TYPE_BUSINESS = 2

    TYPE_CHOICES = ((TYPE_INDIVIDUAL, 'individual'), (TYPE_BUSINESS, 'business'))

    user = models.OneToOneField(User, on_delete=models.DO_NOTHING, primary_key=True)
    external_id = models.CharField(max_length=255, help_text="External user identifier")
    government_id = models.CharField(
        max_length=125, null=True, blank=True, help_text="Government issued user id"
    )
    status = models.CharField(max_length=125)
    verification_status = models.CharField(max_length=124)
    type = models.PositiveSmallIntegerField(
        choices=TYPE_CHOICES, default=TYPE_INDIVIDUAL
    )
    provider = models.ForeignKey(Provider, on_delete=models.DO_NOTHING)
    created = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.user.email


class TransferMethod(models.Model):
    payee = models.ForeignKey(
        Payee, related_name='transfer_methods', on_delete=models.CASCADE
    )
    external_id = models.CharField(
        max_length=255, help_text="External transfer method identifier", unique=True
    )
    type = models.CharField(max_length=125)
    status = models.CharField(max_length=125)
    provider = models.ForeignKey(Provider, on_delete=models.DO_NOTHING)
    currency = models.ForeignKey(Currency, on_delete=models.PROTECT, default=5)
    active = models.BooleanField(default=True)
    created = models.DateTimeField(auto_now_add=True)

    def get_limits_and_fee(self):
        try:
            country = Country.objects.get(code=self.payee.user.country)
            trm_conf = TransferMethodConfiguration.objects.get(
                currency=self.currency,
                type=self.type,
                country=country,
            )
            limits = parseJSONField(trm_conf.limits)
            fee = parseJSONField(trm_conf.fee)
            return {
                "min_amount": Decimal(limits["min"]),
                "max_amount": Decimal(limits["max"]),
                "fee": Decimal(fee["absolute"]),
            }
        except Exception as e:
            return {
                "min_amount": Decimal(2.00)
                if self.type in ["PAYPAL_ACCOUNT", "BANK_ACCOUNT"]
                else Decimal(35.00),
                "max_amount": Decimal(20000.00),
                "fee": Decimal(1.00)
                if self.type in ["PAYPAL_ACCOUNT", "BANK_ACCOUNT"]
                else Decimal(15.00),
            }

    def __str__(self):
        return self.external_id


class Payment(models.Model):
    TYPE_UNKNOWN = 0
    TYPE_ROYALTY = 1
    TYPE_ADVANCE = 2

    TYPE_CHOICES = (
        (TYPE_UNKNOWN, 'unknown'),
        (TYPE_ROYALTY, 'royalty'),
        (TYPE_ADVANCE, 'advance'),
    )

    payee = models.ForeignKey(Payee, related_name='payments', on_delete=models.CASCADE)
    external_id = models.CharField(
        max_length=255, help_text="External payment identifier"
    )
    transfer_method = models.ForeignKey(TransferMethod, on_delete=models.DO_NOTHING)
    currency = models.ForeignKey(Currency, on_delete=models.PROTECT, default=5)
    amount = models.DecimalField(
        max_digits=8, decimal_places=2, help_text="Total amount paid "
    )
    payment_type = models.PositiveSmallIntegerField(
        choices=TYPE_CHOICES, default=TYPE_UNKNOWN
    )
    status = models.CharField(max_length=125)
    created = models.DateTimeField(auto_now_add=True)
    revenue_system_id = models.CharField(
        max_length=255,
        help_text="Revenue system payment identifier",
        blank=True,
        null=True,
    )

    def __str__(self):
        return self.external_id

    def get_currency_display(self):
        return self.currency.code


class Event(models.Model):
    object_id = models.CharField(
        max_length=255, help_text="Payee, TransferMethod or Payment token identifiers"
    )
    created = models.DateTimeField(auto_now_add=True)
    reason = models.CharField(max_length=125, help_text="eg. WEBHOOK")
    initiator = models.CharField(
        max_length=125, help_text="eg SYSTEM, JARVI5, BATCH_TASK"
    )
    payload = JSONField(null=True, blank=True)

    def __str__(self):
        return self.object_id


class TransferMethodConfiguration(models.Model):
    provider = models.ForeignKey(Provider, on_delete=models.DO_NOTHING)
    currency = models.ForeignKey(Currency, on_delete=models.PROTECT, default=5)
    country = models.ForeignKey(Country, on_delete=models.PROTECT, null=True)
    type = models.CharField(max_length=125)
    fee = JSONField(null=True, blank=True)
    limits = JSONField(null=True, blank=True)

    def __str__(self):
        return f'{self.type}({self.currency})'
