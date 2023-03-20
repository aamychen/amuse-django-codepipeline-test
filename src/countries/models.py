from decimal import ROUND_HALF_UP, Decimal

from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models


class Currency(models.Model):
    code = models.CharField(max_length=3)
    name = models.CharField(max_length=255)
    decimals = models.PositiveSmallIntegerField(
        default=2,
        help_text='Number of decimals used when performing Adyen transactions',
    )

    def __str__(self):
        return f'{self.code} - {self.name}'


def next_internal_numeric_code():
    item = Country.objects.aggregate(models.Max('internal_numeric_code'))
    max_id = item['internal_numeric_code__max'] or 0
    return max_id + 1


class Country(models.Model):
    code = models.CharField(primary_key=True, max_length=2, blank=False, null=False)
    name = models.CharField(max_length=255, blank=False, null=False)
    region_code = models.CharField(max_length=2, blank=True, null=True)

    is_adyen_enabled = models.BooleanField(
        default=False, help_text='Enable Adyen payments for this country', db_index=True
    )
    vat_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=4,
        help_text='VAT Percentage for this country, 0-1 (e.g. 10% = 0.1, 25% = 0.25)',
        default=Decimal('0.0'),
    )
    internal_numeric_code = models.SmallIntegerField(
        help_text='Value used internally by Amuse',
        unique=True,
        default=next_internal_numeric_code,
        validators=[MinValueValidator(1), MaxValueValidator(255)],
    )
    is_hyperwallet_enabled = models.BooleanField(
        default=True, help_text='Hyperwallet supports payments for this country'
    )
    dial_code = models.PositiveSmallIntegerField(
        help_text='Country calling code', null=True, blank=True
    )
    is_yt_content_id_enabled = models.BooleanField(
        default=False, help_text='Is You Tube Content ID allowed for this country'
    )

    is_signup_enabled = models.BooleanField(
        default=True, help_text='Enable signups for this country'
    )

    def __str__(self):
        return self.name

    def vat_amount(self, amount):
        return (amount - (amount / (1 + self.vat_percentage))).quantize(
            Decimal('0.01'), rounding=ROUND_HALF_UP
        )

    def vat_percentage_api(self):
        '''The API returns VAT as a percentage instead of value between 0 and 1,
        e.g. "25.00" instead of "0.25"'''
        return self.vat_percentage * 100

    class Meta:
        verbose_name_plural = 'Countries'


class ExchangeRate(models.Model):
    QUARTER_CHOICES = [(x, x) for x in range(1, 5)]

    currency = models.ForeignKey(Currency, on_delete=models.RESTRICT)
    rate = models.DecimalField(
        decimal_places=10, max_digits=12, help_text='Exchange rate from currency to EUR'
    )
    year = models.PositiveSmallIntegerField()
    quarter = models.PositiveSmallIntegerField(choices=QUARTER_CHOICES)

    class Meta:
        unique_together = ('currency', 'year', 'quarter')
