from django.conf import settings
from django.db import models
from django.utils import timezone
from django.db.models import JSONField
from amuse.db.decorators import with_history
from countries.models import Country, Currency
from subscriptions.models import Subscription, SubscriptionPlan
from users.models import User


class PaymentMethod(models.Model):
    external_recurring_id = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        help_text="ID used by payment provider to identify the payment method",
    )
    method = models.CharField(max_length=16, blank=True, null=True)
    summary = models.CharField(
        max_length=4, blank=True, null=True, help_text="Last four digits of card"
    )
    expiry_date = models.DateField(null=True, blank=True)

    user = models.ForeignKey(User, on_delete=models.CASCADE)

    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    def is_expired(self):
        return self.expiry_date and timezone.now().date() >= self.expiry_date


@with_history
class PaymentTransaction(models.Model):
    CATEGORY_UNKNOWN = 0
    CATEGORY_INITIAL = 1
    CATEGORY_RENEWAL = 2
    CATEGORY_RETRY = 3

    CATEGORY_CHOICES = (
        (CATEGORY_UNKNOWN, 'unknown'),
        (CATEGORY_INITIAL, 'initial_purchase'),
        (CATEGORY_RENEWAL, 'renewal'),
        (CATEGORY_RETRY, 'retry'),
    )

    TYPE_UNKNOWN = 0
    TYPE_PAYMENT = 1
    TYPE_AUTHORISATION = 2
    TYPE_FREE_TRIAL = 3
    TYPE_INTRODUCTORY_PAYMENT = 4
    TYPE_CHOICES = (
        (TYPE_UNKNOWN, "unknown"),
        (TYPE_PAYMENT, "payment"),
        (TYPE_AUTHORISATION, "authorisation"),
        (TYPE_FREE_TRIAL, "free_trial"),
        (TYPE_INTRODUCTORY_PAYMENT, "introductory_payment"),
    )

    STATUS_NOT_SENT = 0
    STATUS_PENDING = 1
    STATUS_APPROVED = 2
    STATUS_DECLINED = 3
    STATUS_CANCELED = 4
    STATUS_ERROR = 5

    STATUS_CHOICES = (
        (STATUS_NOT_SENT, "not sent"),
        (STATUS_PENDING, "pending"),
        (STATUS_APPROVED, "approved"),
        (STATUS_DECLINED, "declined"),
        (STATUS_CANCELED, "canceled"),
        (STATUS_ERROR, "error"),
    )

    PLATFORM_UNKNOWN = 0  # used for subs created before PLATFORM field is introduced
    PLATFORM_ANDROID = 1
    PLATFORM_IOS = 2
    PLATFORM_WEB = 3
    PLATFORM_CRON = 4  # backend (amuse-django) usually used for renewals
    PLATFORM_ADMIN = 5  # jarvi5

    PLATFORM_CHOICES = (
        (PLATFORM_UNKNOWN, "unknown"),
        (PLATFORM_ANDROID, "android"),
        (PLATFORM_IOS, "ios"),
        (PLATFORM_WEB, "web"),
        (PLATFORM_CRON, "cron"),
        (PLATFORM_ADMIN, "admin"),
    )

    external_transaction_id = models.CharField(max_length=255, blank=True)
    customer_payment_payload = JSONField(null=True, blank=True)
    external_payment_response = JSONField(null=True, blank=True)
    amount = models.DecimalField(
        max_digits=8, decimal_places=2, help_text="Total amount paid"
    )
    vat_amount = models.DecimalField(
        max_digits=8, decimal_places=2, help_text="VAT part of amount"
    )
    vat_amount_sek = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        null=True,
        help_text="VAT part of amount (in SEK)",
    )
    vat_percentage = models.DecimalField(
        max_digits=5, decimal_places=2, help_text="VAT percentage of amount"
    )
    currency = models.ForeignKey(Currency, on_delete=models.PROTECT, default=5)
    country = models.ForeignKey(
        Country,
        help_text="Country for payment, used to determine VAT on receipt",
        on_delete=models.PROTECT,
    )
    status = models.PositiveSmallIntegerField(
        choices=STATUS_CHOICES, default=STATUS_NOT_SENT
    )
    platform = models.PositiveSmallIntegerField(
        choices=PLATFORM_CHOICES, default=PLATFORM_UNKNOWN
    )
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    subscription = models.ForeignKey(Subscription, on_delete=models.CASCADE)
    plan = models.ForeignKey(SubscriptionPlan, on_delete=models.PROTECT)
    payment_method = models.ForeignKey(
        PaymentMethod, on_delete=models.PROTECT, null=True, blank=True
    )

    paid_until = models.DateTimeField()
    type = models.PositiveSmallIntegerField(choices=TYPE_CHOICES, default=TYPE_UNKNOWN)
    category = models.PositiveSmallIntegerField(
        choices=CATEGORY_CHOICES, default=CATEGORY_UNKNOWN
    )

    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    def __str__(self):
        return "%s (%s, %s)" % (
            self.external_transaction_id,
            self.amount,
            self.get_status_display(),
        )

    @property
    def provider(self):
        return self.subscription.provider

    @property
    def get_amount_formatted_adyen(self):
        price = int(self.amount * pow(10, self.currency.decimals))
        return price

    @property
    def is_introductory(self):
        return self.type == PaymentTransaction.TYPE_INTRODUCTORY_PAYMENT

    def get_currency_display(self):
        return self.currency.code

    def external_url(self):
        """Returns URL to admin for either Adyen or Apple"""
        if self.provider == Subscription.PROVIDER_ADYEN:
            return (
                "https://ca-%s.adyen.com/ca/ca/accounts/showTx.shtml?txType=Payment&pspReference=%s&accountKey=MerchantAccount.%s"
                % (
                    settings.ADYEN_PLATFORM,
                    self.external_transaction_id,
                    settings.ADYEN_MERCHANT_ACCOUNT,
                )
            )
        return None

    def payment_method_and_plan(self):
        return {
            'payment_expiry_date': self.payment_method.expiry_date,
            'payment_method': self.payment_method.method,
            'payment_summary': self.payment_method.summary,
            'plan': self.plan,
            'paid_until': self.paid_until.date(),
        }
